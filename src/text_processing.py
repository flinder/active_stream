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
    name: str, name of the thread.
    '''

    def __init__(self, tp_queue, database, name=None):
        logging.debug('Initializing Text Processor...')
        super(TextProcessor, self).__init__(name=name)
        self.parser = spacy.load('en')
        self.tp_queue = tp_queue
        self.database = database
        self.stoprequest = threading.Event()
        logging.debug('Success.')

    def process_text(self, status):
        '''
        Tokenize and embedd status text

        See the spacy documentation on details about the embedding.

        Arguments:
        ---------------   
        status:
        '''
        doc = self.parser(status['text'])
        status['embedding'] = doc.vector.tolist()
        new = 0
        tot = 0
        for token in doc:
            tot += 1
            if token.vector.sum() == 0:
                new += 1

        status['prop_vectorized'] = new / tot
        #status['tokens'] = {}
        #for token in doc:
        #    token = token.lemma_
        #    token = token.replace('.', '')
        #    token = token.replace('$', '')
        #    status['tokens'][token] = status['tokens'].get(token, 0) + 1
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
