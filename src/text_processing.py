import threading
import logging
import spacy

import shared


class TextProcessor(threading.Thread):
    '''
    Ingests status text, updates global vocabulary and document frequency
    counts. Embedds status text in word2vec space and appends embedded
    representation to status object.

    Arguments:
    --------------- 
    queues: dict containing all queues to pass data between treads.
    name: str, name of the thread.
    '''

    def __init__(self, queues, name=None):
        logging.debug('Initializing Text Processor...')
        super(TextProcessor, self).__init__(name=name)
        self.parser = spacy.load('en')
        self.queues=queues
        logging.debug('Success.')

    def process_text(self, status):
        '''
        Tokenize and embedd status text

        See the spacy documentation on details about the embedding.

        Arguments:
        ---------------   
        status:
        '''
        doc = self.parser.tokenizer(status['text'])
        status['embedding'] = doc.vector.tolist()
        return status

    def run(self):
        logging.debug('Running.')
        while not shared.TERMINATE:
            if not self.queues['text_processor'].empty():
                logging.debug('Received tweet')
                status = self.queues['text_processor'].get()
                status = self.process_text(status)
                logging.debug('Processed tweet')
                self.queues['classifier'].put(status)
        logging.debug('Terminating.')
        self.cleanup()

    def cleanup(self):
        return None
