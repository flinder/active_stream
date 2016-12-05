import tweepy
import queue
import threading
import time
import numpy as np
import spacy
import logging

from pprint import pprint
from sklearn.linear_model import LogisticRegression

from twitter_credentials import credentials


class Listener(tweepy.StreamListener):

    def on_status(self, status):
        status = self.filter_status(status) 
        if status is None:
            return True
        else:
            status = self.amend_status(status)
            text_processing_queue.put(status)
            return True

    def on_error(self, status):
        raise ValueError('Twitter API Exception: {}'.format(status))

    def amend_status(self, status):
        '''
        Adds relevance fields to status.
        '''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        return status

    def filter_status(self, status):
        '''
        Additional filters to remove statuses. Also converts tweepy Status
        object to dictionary.
        '''
        status = status._json 
        if status['lang'] != 'en':
            return None
        else:
            return status


class StreamingThread(threading.Thread):
    '''
    Connects to Twitter API and directs incoming statuses to the respective 
    queues.
    '''
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Streamer...')
        super(StreamingThread, self).__init__(name=name)
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        global keyword_monitor
        keywords = [str(keyword_monitor[kw]) for kw in keyword_monitor]
        logging.debug('Tracking: {}'.format(keywords))
        while True:
            try:
                ok = stream.filter(track=keywords)
            except KeyboardInterrupt:
                stream.disconnect()
                break


class TextProcessingThread(threading.Thread):
    '''
    Ingests status text, updates global vocabulary and document frequency
    counts. Embedds status text in word2vec space and appends embedded
    representation to status object.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Text Processor...')
        super(TextProcessingThread, self).__init__(name=name)
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
        

class ClassifierThread(threading.Thread):
    '''
    Classifies statuses as relevant / irrelevant based on classification model
    trained by TrainerThread.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Classifier...')
        super(ClassifierThread, self).__init__(name=name)
        self.clf = None
        logging.debug('Success')

    def run(self):
        logging.debug('Running.')
        while True:
            if not classifier_queue.empty():
                status = classifier_queue.get()
                status = self.classify_status(status)
                logging.debug('Received tweet. Probability relevant: {}'.format(
                    status['probability_relevant']))
                dummy_database.append(status)
    
    def classify_status(self, status):

        if self.clf is None and model_queue.empty():
            prob = 0.5
        else:
            if not model_queue.empty():
                logging.debug('Acquiring Model')
                self.clf = model_queue.get()
            X = status['embedding'].reshape(1, -1)
            pred_prob = self.clf.predict_proba(X) 
            prob = pred_prob[0][1]

        status['probability_relevant'] = prob
        if prob < 0.5:
            status['classifier_relevant'] = False
        else:
            status['classifier_relevant'] = True
        # Send uncertain statuses to annotation module
        if prob > 0.4 and prob < 0.6:
           annotation_queue.put(status) 
        
        # Send all tweets to KWmanager
        kw_queue.put(status)

        return status


class TrainerThread(threading.Thread):
    '''
    (Re)Trains classification model.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Trainer...')
        super(TrainerThread, self).__init__(name=name)
        self.clf = LogisticRegression()
        logging.debug('Success')

    def train_model(self):
        global RUN_TRAINER

        # Transform data
        y = []
        X = []
        for d in dummy_database:
            if d['manual_relevant'] is not None:
                X.append(d['embedding'])
                y.append(d['manual_relevant'])
        X = np.array(X)
        y = np.array(y)
        
        # Fit model
        self.clf.fit(X, y) 

        # Pass model to classifier
        model_queue.put(self.clf)
        RUN_TRAINER = False
        
    def run(self):
        global RUN_TRAINER

        logging.debug('Running.')
        # Wait for first positive / negative annotation
        while not ONE_POSITIVE or not ONE_NEGATIVE:
            pass

        # After that run everytime prompted by the annotator thread
        while True:
            if RUN_TRAINER:
                logging.debug('Retraining Model...')
                self.train_model()
                logging.debug('Trained Model.')
            else:
                pass


class AnnotationThread(threading.Thread):
    '''
    Handles manual annotations.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Annotator...')
        super(AnnotationThread, self).__init__(name=name)
        logging.debug('Success.')

    def run(self):
        global ONE_POSITIVE
        global ONE_NEGATIVE
        global RUN_TRAINER

        logging.debug('Running.')
        while True:
            if not annotation_queue.empty():
                status = annotation_queue.get()
                while True:
                    print(status['text'])
                    annotation = input('Relevant? (y/n)')
                    if annotation == 'y':
                        status['manual_relevant'] = True
                        ONE_POSITIVE = True
                        RUN_TRAINER = True 
                        break
                    elif annotation == 'n':
                        status['manual_relevant'] = False
                        ONE_NEGATIVE = True
                        RUN_TRAINER = True
                        break
                    else:
                        continue
                dummy_database.append(status)



class KWManagerThread(threading.Thread):
    '''
    Takes batches of incoming statuses and suggests new keywords based on
    co-occurence with existing (high quality) keywords. Also monitors keywords
    and controls activation / deactivation

    # NOT IMPLEMENTED YET
    '''
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Annotator...')
        super(KWExpanderThread, self).__init__()
        logging.debug('Success.')

    def get_all(q, n_items):
        items = []
        for i in range(0, n_items):
            try:
                items.append(q.get_nowait())
            except Empty:
                break
        return items 

    def run(self):
        global keyword_monitor
        global seed
        global BUF_SIZE

        logging.debug('Running...')

        # Activate seed keywords
        keyword_monitor[str(seed)] = seed
        seed.activate()

        while True:
            # Check incoming tweets and update keyword performance
            if not kw_queue.empty():
                all_new = get_all(kw_queue, BUF_SIZE)
            
            # [Store tokenized tweet text with Text Processor]

            # Assess keyword performance and deactivate if necessary
            

            # Propose new keywords 
            pass


class Keyword(object):
    '''
    Keyword to track with Twitter API
    '''    

    def __init__(self, word, user_word=False):
        self.word = word
        self.n_relevant = 0
        self.n_irrelevant = 0
        self.active = False
        self.history = []
        self.user_word = user_word

    def  __str__(self):
        return self.word

    def activate(self):
        self.active = True
        self.history.append(('activated', time.time()))

    def deactivate(self):
        self.active = False
        self.history.append(('deactivated', time.time()))

   

if __name__ == "__main__":
    
    # Get authentication data
    consumer_key = credentials['coll_1']['consumer_key']
    consumer_secret = credentials['coll_1']['consumer_secret']
    access_token = credentials['coll_1']['access_token']
    access_token_secret = credentials['coll_1']['access_token_secret']
    
    # Set up authentication
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    # Set global constants 
    BUF_SIZE = 1000

    # Set global variables
    ONE_POSITIVE = False
    ONE_NEGATIVE = False
    RUN_TRAINER = False

    # Set up data structures
    text_processing_queue = queue.Queue(BUF_SIZE)
    classifier_queue = queue.Queue(BUF_SIZE)
    annotation_queue = queue.Queue(BUF_SIZE)
    model_queue = queue.Queue(1)
    kw_queue = queue.Queue(BUF_SIZE)
    keyword_monitor = {}
    dummy_database = []

        # Set up stream
    listener = Listener()
    stream = tweepy.Stream(auth=auth, listener=listener)

    # Seed input
    seed = Keyword('merkel', user_word=True)
    keyword_monitor[str(seed)] = seed

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s (%(threadName)s) %(message)s',
                        filename='debug.log')
    
    # Initialize Threads
    streamer = StreamingThread(name='Streamer')
    text_processor = TextProcessingThread(name='Text Processor')
    classifier = ClassifierThread(name='Classifier')
    annotator = AnnotationThread(name='Annotator')
    trainer = TrainerThread(name='Trainer')
    
    # Start Threads
    streamer.start()
    text_processor.start()
    classifier.start()
    annotator.start()
    trainer.start()


