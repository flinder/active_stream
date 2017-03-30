import threading
import logging
import spacy
import queue


class TextProcessor(threading.Thread):
    '''
    Ingests status text, updates global vocabulary and document frequency
    counts. Embedds status text in word2vec space and appends embedded
    representation to status object.

    Arguments:
    --------------- 
    tp_queue: Queue containing work (statuses) for the text processor
    database: MongoDB connection
    dictionary: A gensim dictionary object
    name: str, name of the thread.
    stopwords: list, list of stopwords to enforce
    '''

    def __init__(self, tp_queue, database, dictionary, dict_lock, name=None, 
                 stopwords=[]):
        logging.debug('Initializing Text Processor...')
        super(TextProcessor, self).__init__(name=name)
        self.parser = spacy.load('en')
        self.tp_queue = tp_queue
        self.database = database
        self.stoprequest = threading.Event()
        self.stoplist = set(stopwords)
        self.dictionary = dictionary
        self.dict_lock = dict_lock
        logging.debug('Success.')

    def process_text(self, status):
        '''
        Tokenize status text

        Arguments:
        ---------------   
        status: dict, the tweet to process
        '''

        doc = self.parser(status['text'])
        lemmas = [t.lemma_ for t in doc if t.lemma_ not in self.stoplist] 
        with self.dict_lock:
            status['bow'] = self.dictionary.doc2bow(lemmas, allow_update=True)
            # Get id -> tokn mapping
            self.dictionary.id2token = {v: k 
                                        for k, v 
                                        in self.dictionary.token2id.items()}
        return status


    def run(self):
        logging.debug('Running.')
        while not self.stoprequest.isSet():
            try:
                status = self.tp_queue.get(True, 1)
                logging.debug('Received tweet')
                status = self.process_text(status)
                logging.debug('Processed tweet. Inserting to DB')
                self.database.insert(status)
            except queue.Empty:
                continue

        logging.debug('Terminating.')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(TextProcessor, self).join(timeout)
