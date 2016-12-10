import threading
import logging
import spacy

class TextProcessor(threading.Thread):
    '''
    Ingests status text, updates global vocabulary and document frequency
    counts. Embedds status text in word2vec space and appends embedded
    representation to status object.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Text Processor...')
        super(TextProcessor, self).__init__(name=name)
        self.parser = spacy.load('en')
        logging.debug('Success.')

    def process_text(self, status):
        doc = self.parser.tokenizer(status['text'])
        status['embedding'] = doc.vector
        return status

    def run(self):
        logging.debug('Running.')
        while True:
            if not text_processing_queue.empty():
                logging.debug('Received tweet')
                status = text_processing_queue.get()
                status = self.process_text(status)
                classifier_queue.put(status)
 
