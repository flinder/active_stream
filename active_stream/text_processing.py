import threading
import logging
import spacy
import queue
import re
import string

from urllib.parse import urlparse

class TextProcessor(threading.Thread):
    '''
    Ingests status text, updates global vocabulary and document frequency
    counts. Embedds status text in word2vec space and appends embedded
    representation to status object.

    Arguments:
    --------------- 
    data: data structures see app.py for details
    '''

    def __init__(self, data):
        super(TextProcessor, self).__init__(name='Text Processor')
        self.parser = spacy.load('en')
        self.tp_queue = data['queues']['text_processing']
        self.database = data['database']
        self.stoprequest = threading.Event()
        self.stoplist = set()
        self.dictionary = data['dictionary']
        self.repl = ['\\', '/', '-']

    def remove_text_by_idx(self, text, indices):
        '''
        Remove sections of text by start and end indices 
        indices can't be overlapping

        text: str
        indices: list of tuples
        '''
        sorted_idcs = sorted(indices, key=lambda x: x[0], reverse=True)
        for pair in sorted_idcs:
            text = text[:pair[0]] + text[pair[1]:]
        return text


    def process_text(self, status):
        '''
        Tokenize status text

        Arguments:
        ---------------   
        status: dict, the tweet to process
        '''
        
        # Collect all fields of the tweet that might contain information on
        # content

        # Fields that allways exist
        screen_name = status['user']['screen_name']
        name = status['user']['name']
        text = status['text']

        # Entities
        ## Hashtags:
        hashtags = status['entities']['hashtags']
        out_hashtags = []
        idxs = []
        if len(hashtags) > 0:
            for ht in hashtags:
                out_hashtags.append('#' + ht['text'])
                idxs.append(ht['indices'])

        ## urls 
        urls = status['entities']['urls']
        out_urls = []
        if len(urls) > 0:
            for url in urls:
                if url['url'] == '':
                    continue
                parsed = urlparse(url['expanded_url'])
                path = parsed[2].translate({ord(c):' ' for c in self.repl})
                out_urls.extend([parsed[1]] + path.split(' '))
                idxs.append(url['indices'])

        ## user_mentions 
        users = status['entities']['user_mentions']
        out_users = []
        if len(users) > 0:
            for user in users:
                out_users.append('@' + user['screen_name'])
                idxs.append(user['indices'])
                   
        # Remove entities from text
        text = self.remove_text_by_idx(text, idxs)
        
        # Parse (tokenize and lemmatize) the remaining text field
        doc = self.parser(text)
        lemmas = [t.lemma_ for t in doc if t.lemma_ not in self.stoplist] 

        # Put all the information together
        info = (lemmas + [screen_name] + [name] + out_hashtags + out_urls + 
                out_users)
        
        l_0 = len(self.dictionary)
        status['bow'] = self.dictionary.doc2bow(info, allow_update=True)
        l_1 = len(self.dictionary)
        status['dict_size'] = l_1

        # Get id -> tokn mapping
        if l_1 > l_0:
            self.dictionary.id2token = {v: k 
                                        for k, v 
                                        in self.dictionary.token2id.items()}
        return status


    def run(self):
        logging.debug('Ready!')
        while not self.stoprequest.isSet():
            try:
                status = self.tp_queue.get(True, 1)
                status = self.process_text(status)
                self.database.insert(status)
            except queue.Empty:
                continue

        logging.debug('Stopped')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(TextProcessor, self).join(timeout)
