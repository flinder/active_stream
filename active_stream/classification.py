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

    Arguments:
    --------------- 
    database: MongoDB connection
    model: Queue object for passing the model from Trainer to Classifier 
    dictionary: A gensim dictionary object
    threshold: Threshold in predicted probability to classify to relevant /
        irrelevant.
    name: str, name of the thread.
    batchsize: How many statues to classifiy in one batch
    max_clf_procs: Maximum number of processors to allocate to classifier
    '''

    def __init__(self, database, model, dictionary, threshold=0.5,
                 name=None, batchsize=1000, max_clf_procs=1):
        super(Classifier, self).__init__(name=name)
        self.clf = DummyClf(threshold)
        self.database = database
        self.threshold = threshold
        self.stoprequest = threading.Event()
        self.batchsize = batchsize
        self.model_queue = model
        self.dictionary = dictionary
        self.clf_version = 0


    def run(self):
        logging.info('Ready!')
        first = True
        while not self.stoprequest.isSet():

            if not self.model_queue.empty():
                logging.info(f'Received new model (version {self.clf_version}')
                self.clf = self.model_queue.get()
                self.clf_version += 1
                to_classify = self.database.find({'manual_relevant': None})

            else:
                to_classify = self.database.find({'probability_relevant': None,
                                                  'manual_relevant': None})
        
            count_new = to_classify.count()
            if count_new > 0:
                batch = []
                for status in to_classify:
                    # Ignore skipped statuses
                    if status['manual_relevant'] == -1:
                        continue
                    batch.append(status)
                    if len(batch) == self.batchsize:
                        self.process_batch(batch)
                        batch = []

                if len(batch) > 0:
                    self.process_batch(batch)
            sleep(1)

        logging.info("Stopped.")

    def process_batch(self, batch):
        '''
        Classify a batch of statuses as relevant / irrelevant based on the 
        current model

        batch: list, of dicts containing statuses to be proceessed
        '''
         
        corpus = [status['bow'] for status in batch] 

        corpus = [0] * len(batch)
        dict_sizes = np.zeros(len(batch))
        for i,s in enumerate(batch):
            corpus[i] = s['bow']
            dict_sizes[i] = s['dict_size']

        n_terms_dict = max(dict_sizes)
        n_terms_model = self.clf.coef_.shape[1]
        if n_terms_model > n_terms_dict:
            n_terms_dict = n_terms_model

        X = matutils.corpus2dense(corpus, num_docs=len(corpus),
                                  num_terms=n_terms_dict).transpose()
        
        if n_terms_dict > n_terms_model:
            X = X[:, :n_terms_model]
        
        probs = self.clf.predict_proba(X)[:, 1]

        bulk = self.database.initialize_unordered_bulk_op()
        for status, prob in zip(batch, probs):  
            ap = (prob - 0.5)**2
            if prob < 0.5:
                clf_rel = False
            else:
                clf_rel = True

            bulk.find({'_id': status['_id']}).update(
                      {"$set":{'probability_relevant': prob,
                               'classifier_relevant': clf_rel,
                               'annotation_priority': ap,
                               'clf_version': self.clf_version}})

        msg = bulk.execute() 

    def join(self, timeout=None):
        logging.info("Received stoprequest")
        self.stoprequest.set()
        super(Classifier, self).join(timeout)


class Trainer(threading.Thread):
    '''
    (Re)Trains classification model.

    When `ONE_POSITIVE` and `ONE_NEGATIVE` and `RUN_TRAINER` are set to True (by
    `Annotator()`, (re-)train the model and put it into `queues['model']

    Arguments:
    --------------- 
    database: pymongo connection to database
    model: queue object to send model to classifier
    clf: A classifier object. Must contain a `fit(X, y)` method (see sk learn
        models)
    train_trigger: threading.Event to trigger training of new model (triggered
        by annotator)
    dictionary: current dictionary from text processor
    most_important_features: most important features

    '''

    def __init__(self, database, model, clf, train_trigger, dictionary, 
                 most_important_features, message_queue, stream, name=None):
        super(Trainer, self).__init__(name=name)
        self.clf = clf
        self.model_queue = model
        self.trigger = train_trigger 
        self.stoprequest = threading.Event()
        self.database = database
        self.dictionary = dictionary
        self.mif_queue = most_important_features
        self.clf_version = 0
        self.message_queue = message_queue
        self.streamer = stream
        self.mif_stopwords = set([' ', '-PRON-', '.', '-', ':', ';',
                                  '&', 'amp'])

    def train_model(self):
        '''
        (Re)train the model on all annotated tweets in the db
        '''
        # Transform data y = []
        corpus = []
        dict_lens = []
        y = []
        # Get all manually annotated docs from db
        cursor = self.database.find({'manual_relevant': {'$ne': None}}) 
        for d in cursor:
            # Ignore skipped statuses
            if d['manual_relevant'] == -1:
                continue
            corpus.append(d['bow'])
            dict_lens.append(d['dict_size'])
            y.append(d['manual_relevant'])

        X = matutils.corpus2dense(corpus, num_docs=len(corpus),
                                  num_terms=max(dict_lens)).transpose()
        y = np.array(y)
        
        # Fit model
        #self.clf.partial_fit(X, y, classes=np.array([0, 1]))
        self.clf.fit(X, y)
        mif_indices = sorted(enumerate(self.clf.coef_[0]), key=lambda x: x[1], 
                             reverse=True)
        mif_indices = [x[0] for x in mif_indices]
        mif = []
        # Update list of tracked keywords
        self.mif_stopwords.update([x.lower() for x in self.streamer.keywords])
        for id_ in mif_indices:
            word = self.dictionary.id2token[id_]
            if word not in self.mif_stopwords:
                mif.append(word)
            else:
                continue
            if len(mif) == 10:
                break
        self.mif_queue.put(mif)

        # Pass model to classifier
        self.clf_version += 1
        self.model_queue.put(self.clf)

        
    def run(self):
        logging.info('Ready!')
        # Wait for first positive / negative annotation
        while not self.stoprequest.isSet():
        
            if self.trigger.isSet():
                logging.info(f'Training new model (version {self.clf_version}')
                self.message_queue.put("Training new model")
                self.train_model()
                self.trigger.clear()
            else:
                sleep(0.05)

        logging.info('Stopped')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Trainer, self).join(timeout)
