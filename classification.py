import threading
import logging

class Classifier(threading.Thread):
    '''
    Classifies statuses as relevant / irrelevant based on classification model
    trained by TrainerThread.
    '''

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Classifier...')
        super(Classifier, self).__init__(name=name)
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


class Trainer(threading.Thread):
    '''
    (Re)Trains classification model.
    '''

    def __init__(self, clf, group=None, target=None, name=None, args=(), 
            kwargs=None, verbose=None):
        logging.debug('Initializing Trainer...')
        super(Trainer, self).__init__(name=name)
        self.clf = clf
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


