import threading
import multiprocessing
import logging
import numpy as np
import queue
import scipy.sparse

from time import sleep
from gensim import matutils


class DummyClf(object):

    def __init__(self, value):
        self.value = value
        self.coef_ = np.array([None], ndmin=2)

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
    dictionary: A gensim dictionary object
    dict_lock: threading.Lock object for dictionary use
    threshold: Threshold in predicted probability to classify to relevant /
        irrelevant.
    ucr_size: size of interval to both sides of threshold to classify tweets as 
        uncertain (uncertainty region).  batchsize: size of batches that are classified at a time
    name: str, name of the thread.
    '''

    def __init__(self, database, model, dictionary, dict_lock, threshold=0.5, ucr_size=0.1, 
                 name=None, batchsize=1000, max_clf_procs=1):

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
        self.dictionary = dictionary
        self.dict_lock = dict_lock

        logging.debug('Success')

    def run(self):

        logging.debug('Running.')
        first = True
        while not self.stoprequest.isSet():

            if not self.model_queue.empty():
                logging.debug('Received new model')
                self.clf = self.model_queue.get()
                with self.dict_lock:
                    n_terms = len(self.dictionary)
                    to_classify = self.database.find({'manual_relevant': None})

            else:
                with self.dict_lock:
                    n_terms = len(self.dictionary)
                    to_classify = self.database.find(
                            {'probability_relevant': None,
                             'manual_relevant': None})
            
            count_new = to_classify.count()
            if count_new > 0:
                logging.debug('{} new statuses. Classifying...'.format(count_new))
                batch = []
                for status in to_classify:
                    batch.append(status)
                    if len(batch) == self.batchsize:
                        self.process_batch(batch, n_terms)
                        batch = []

                if len(batch) > 0:
                    self.process_batch(batch, n_terms)
            sleep(0.1)

        logging.debug('Terminating.')

    def process_batch(self, batch, n_terms):
        '''
        Classify a batch of statuses as relevant / irrelevant based on the 
        current model

        batch: list, of dicts containing statuses to be proceessed
        n_terms: number of terms in dictionary at query time
        '''
        
        corpus = [status['bow'] for status in batch] 
        X = matutils.corpus2dense(corpus, num_docs=len(corpus),
                                  num_terms=n_terms).transpose()
        n_features = self.clf.coef_.shape[1]
        X = X[:, :n_features]
        probs = self.clf.predict_proba(X)[:, 1]

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

    def __init__(self, database, model, clf, train_trigger, dictionary,
                 dict_lock, name=None):
        logging.debug('Initializing Trainer...')
        super(Trainer, self).__init__(name=name)
        self.clf = clf
        self.model_queue = model
        self.trigger = train_trigger 
        self.stoprequest = threading.Event()
        self.database = database
        self.dictionary = dictionary
        self.dict_lock = dict_lock
        logging.debug('Success')

    def train_model(self):
        '''
        (Re)train the model on all annotated tweets in the db
        '''
        # Transform data y = []
        corpus = []
        y = []
        # Get all manually annotated docs from db
        cursor = self.database.find({'manual_relevant': {'$ne': None}}) 
        for d in cursor:
            corpus.append(d['bow'])
            y.append(d['manual_relevant'])

        X = matutils.corpus2dense(corpus, num_docs=len(corpus),
                                  num_terms=len(self.dictionary)).transpose()
        y = np.array(y)
        
        # Fit model
        #self.clf.partial_fit(X, y, classes=np.array([0, 1]))
        self.clf.fit(X, y)
        mif_indices = sorted(enumerate(self.clf.coef_[0]), key=lambda x: x[1], 
                             reverse=True)
        mif_indices = [x[0] for x in mif_indices]
        with self.dict_lock: 
            mif = [self.dictionary.id2token[id_] for id_ in mif_indices[:10]]
        logging.debug("Most important features: {}".format(mif))

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
