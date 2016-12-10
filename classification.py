import threading
import logging
import numpy as np

import shared

class Classifier(threading.Thread):
    '''
    Classifies statuses as relevant / irrelevant based on classification model
    trained by TrainerThread.
    '''

    def __init__(self, queues, group=None, target=None, name=None, args=(), 
            kwargs=None, verbose=None):
        logging.debug('Initializing Classifier...')
        super(Classifier, self).__init__(name=name)
        self.clf = None
        self.queues = queues
        logging.debug('Success')

    def run(self):

        logging.debug('Running.')
        while True:
            if not self.queues['classifier'].empty():
                status = self.queues['classifier'].get()
                status = self.classify_status(status)
                logging.debug('Received tweet. Probability relevant: {}'.format(
                    status['probability_relevant']))
                #self.queues['database'].put(status)
                shared.database_lock.acquire()
                shared.database.append(status)
                shared.database_lock.notify_all()
                shared.database_lock.release()
    
    def classify_status(self, status):

        if self.clf is None and self.queues['model'].empty():
            prob = 0.5
        else:
            if not self.queues['model'].empty():
                logging.debug('Acquiring Model')
                self.clf = self.queues['model'].get()
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
           self.queues['annotator'].put(status) 
        
        # Send all tweets to KWmanager
        #queue.put(status)

        return status


class Trainer(threading.Thread):
    '''
    (Re)Trains classification model.
    '''

    def __init__(self, clf, queues, group=None, target=None, name=None, args=(), 
            kwargs=None, verbose=None):
        logging.debug('Initializing Trainer...')
        super(Trainer, self).__init__(name=name)
        self.clf = clf
        self.queues = queues
        logging.debug('Success')

    def train_model(self):
        # Transform data y = []
        X = []
        y = []
        shared.database_lock.acquire()
        for d in shared.database:
            if d['manual_relevant'] is not None:
                X.append(d['embedding'])
                y.append(d['manual_relevant'])

        shared.database_lock.notify_all()
        shared.database_lock.release()

        X = np.array(X)
        y = np.array(y)
        
        # Fit model
        self.clf.fit(X, y) 

        # Pass model to classifier
        self.queues['model'].put(self.clf)
        shared.RUN_TRAINER = False
        
    def run(self):

        logging.debug('Running.')
        # Wait for first positive / negative annotation
        while not shared.ONE_POSITIVE or not shared.ONE_NEGATIVE:
            pass

        # After that run everytime prompted by the annotator thread
        while True:
            if shared.RUN_TRAINER:
                logging.debug('Retraining Model...')
                self.train_model()
                logging.debug('Trained Model.')
            else:
                pass


