import threading
import multiprocessing
import logging
import numpy as np
import queue
from time import sleep


class DummyClf(object):

    def __init__(self, value):
        self.value = value

    def predict_proba(self, X):
        b = np.array([self.value] * X.shape[0])
        a = np.array([1 - self.value] * X.shape[0])
        return np.column_stack((a,b))

class Classifier(threading.Thread):
    '''
    Classifies statuses as relevant / irrelevant based on classification model
    trained by `Trainer()` and placed into `queues['model']`.

    Appends to the status object a field 'classifier_relevant' containing a
    binary classification (bool) and a field 'probability_relevant' containing
    the probability this classification is based on.

    If a status is uncertain (predicted probability in threshold +/- ucr_size) 
    the status' field to_annotate is set to True.

    Arguments:
    --------------- 
    database: MongoDB connection
    model: Queue object for passing the model from Trainer to Classifier 
    threshold: Threshold in predicted probability to classify to relevant /
        irrelevant.
    ucr_size: size of interval to both sides of threshold to classify tweets as 
        uncertain (uncertainty region).  batchsize: size of batches that are classified at a time
    name: str, name of the thread.
    '''

    def __init__(self, database, model, threshold=0.5, ucr_size=0.1, name=None,
            batchsize=1000, max_clf_procs=1):

        logging.debug('Initializing Classifier...')

        super(Classifier, self).__init__(name=name)

        self.clf = DummyClf(threshold)
        self.database = database
        self.threshold = threshold
        self.ucr_lo = threshold - ucr_size
        self.ucr_hi = threshold + ucr_size
        self.stoprequest = threading.Event()
        self.batchsize = batchsize
        self.model_queue = model

        logging.debug('Success')

    def run(self):

        logging.debug('Running.')
        first = True
        while not self.stoprequest.isSet():

            if not self.model_queue.empty():
                logging.debug('Received new model')
                self.clf = self.model_queue.get()
                to_classify = self.database.find(
                     {'manual_relevant': None})
            else:
                to_classify = self.database.find(
                        {'probability_relevant': None,
                         'manual_relevant': None})
            
            count_new = to_classify.count()
            if count_new > 0:
                logging.debug('{} new statuses. Classifying...'.format(count_new))
                self.classify_statuses(to_classify)
            sleep(2)

        logging.debug('Terminating.')


    def classify_statuses(self, cursor):
        '''
        Classify and update in database results from a database query
        Arguments:
        cursor: A mongo db cursor
        '''
        batch = []
        for status in cursor:
            batch.append(status)
            if len(batch) == self.batchsize:
                self.process_batch(batch)
                batch = []

        if len(batch) > 0:
            self.process_batch(batch)

    
    def process_batch(self, batch):
        '''
        Classify a batch of statuses as relevant / irrelevant based on the 
        current model
        '''
        
        # Get predictions for the model
        X = np.array([s['embedding'] for s in batch])
        probs = self.clf.predict_proba(X)[:, 1]
        logging.debug('Probabilities: {}'.format(probs))

        bulk = self.database.initialize_unordered_bulk_op()
        for status, prob in zip(batch, probs):  
            if self.ucr_lo < prob < self.ucr_hi:
                to_annotate = True
            else:
                to_annotate = False

            bulk.find({'_id': status['_id']}).update(
                      {"$set":{'probability_relevant': prob,
                               'to_annotate': to_annotate}})
 
        msg = bulk.execute() 

        logging.debug('bulk update: {}'.format(msg))


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Classifier, self).join(timeout)


class Trainer(threading.Thread):
    '''
    (Re)Trains classification model.

    When `ONE_POSITIVE` and `ONE_NEGATIVE` and `RUN_TRAINER` are set to True (by
    `Annotator()`, (re-)train the model and put it into `queues['model']

    Arguments:
    --------------- 
    queues, dict containing all queues for passing data between threads (see
        main script)
    clf: A classifier object. Must contain a `fit(X, y)` method (see sk learn
        models)
    '''

    def __init__(self, database, model, clf, train_trigger, name=None):
        logging.debug('Initializing Trainer...')
        super(Trainer, self).__init__(name=name)
        self.clf = clf
        self.model_queue = model
        self.trigger = train_trigger 
        self.stoprequest = threading.Event()
        self.database = database
        logging.debug('Success')

    def train_model(self):
        '''
        (Re)train the model on all annotated tweets in the db
        '''
        # Transform data y = []
        X = []
        y = []
        # Get all manually annotated docs from db
        cursor = self.database.find({'manual_relevant': {'$ne': None}}) 
        for d in cursor:
            X.append(d['embedding'])
            y.append(d['manual_relevant'])

        X = np.array(X)
        y = np.array(y)
        
        # Fit model
        self.clf.partial_fit(X, y, classes=np.array([0, 1]))

        # Pass model to classifier
        self.model_queue.put(self.clf)
        
    def run(self):

        logging.debug('Running.')
        # Wait for first positive / negative annotation
        while not self.stoprequest.isSet():
        
            if self.trigger.isSet():
                logging.debug('Training new model')
                self.train_model()
                logging.debug('Finished training')
                self.trigger.clear()
            else:
                sleep(0.05)

        logging.debug('Terminating.')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Trainer, self).join(timeout)
