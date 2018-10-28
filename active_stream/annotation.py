import threading
import logging
import queue
import pymongo

import numpy as np

from time import sleep

class Annotator(threading.Thread):
    '''
    Handles manual annotations.

    Queries database for uncertain statuses, presents and presents them to the
    user.     
    
    Arguments:
    ---------------  
    database: pymongo connection
    train_event: threading event. To communicate with Trainer
    train_threshold: int, number of annotations (for each class) before training
        starts.
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, data, train_threshold=1):
        super(Annotator, self).__init__(name='Annotator')
        self.database = data['database']
        self.train = data['events']['train_model']
        self.stoprequest = threading.Event()
        self.n_positive = False
        self.n_negative = False
        self.train_threshold = train_threshold
        self.annotation_response = data['queues']['annotation_response']
        self.socket = data['socket']
        self.annotated_text = {}
        self.message_queue = data['queues']['messages']
        self.n_trainer_triggered = 0
        self.clf_performance = {
                'true_positive': 0,
                'true_negative': 0,
                'false_positive': 0,
                'false_negative': 0
                }
        self.first = True
        

    def run(self):
        logging.debug('Ready!')
        while not self.stoprequest.isSet():

            # Every third annotation is an evaluation run
            eval_run = np.random.choice([True, False], size=1, p=[0.3,0.7])[0]

            # Look for work:
            not_annotated = self.database.find({'manual_relevant': None,
                                                'probability_relevant': {
                                                    '$ne': None
                                                    }})
            
            # If no work, wait and try again
            if not_annotated.count() == 0:
                if self.first:
                    self.socket.emit('display_tweet', {'tweet_id': 'waiting'})
                    self.first = False
                sleep(0.05)
                continue
            
            if not eval_run:
                work = not_annotated.sort('annotation_priority', 
                                          pymongo.ASCENDING).limit(1)
            else:
                work = not_annotated.limit(1)
            
            for status in work:
                
                # Check if user annotated a tweet with the same text before
                if status['text'] in self.annotated_text:
                    response = self.annotated_text[status['text']]
                else:
                    # Empty the queue in case the user clicked twice or while
                    # waiting
                    if self.annotation_response.full():
                        self.annotation_response.get()
                    id_ = str(status['id'])
                    guess = str(round(status['probability_relevant'], 3))
                    logging.debug(f'Sending tweet for annotation. Id: {id_}'
                                  f'evaluation: {eval_run}')
                    self.socket.emit('display_tweet', {'tweet_id': id_,
                                                       'guess': guess,
                                                       'eval': str(eval_run)})
                    if eval_run:
                        p = round(status['probability_relevant'], 2)
                        self.message_queue.put('This is an evaluation Tweet '
                                               'I guess it is relevant with '
                                               f'probability {p}')
                
                while not self.stoprequest.isSet():
                    try:
                        response = self.annotation_response.get(timeout=0.1)
                        logging.debug(f'Received response {response}')
                        break
                    except queue.Empty as e:
                        continue

                if response == 'relevant':
                    out = True
                    self.n_positive += 1
                elif response == 'irrelevant':
                    out = False
                    self.n_negative += 1
                elif response == 'skip':
                    out = -1
                elif response == 'refresh':
                    continue
                    
                else:
                    raise ValueError('Received invalid response from interface')
                self.first = True

                # Store the text in memory to not ask twice
                self.annotated_text[status['text']] = out

                # Evaluate classifier
                if self.n_trainer_triggered > 0 and eval_run:
                    guess = bool(round(status['probability_relevant'], 0))
                    self.clf_performance[self.evaluate_guess(guess, out)] += 1

                # Update record in DB
                msg = self.database.update(
                        {'_id': status['_id']}, 
                        {'$set': {'manual_relevant': out,
                                  'probability_relevant': int(out),
                                  'annotation_priority': None,
                                  'clf_version': float('inf')}}
                        )

                # Trigger trainer if necessary
                threshold = (self.n_trainer_triggered+1) * self.train_threshold
                if (self.n_positive > threshold and 
                    self.n_negative > threshold):
                    self.train.set()
                    self.n_trainer_triggered += 1

        logging.debug('Stopped.')

    def evaluate_guess(self, guess, annotation):
        if guess and annotation:
            return 'true_positive'
        if not guess and not annotation:
            return 'true_negative'
        if not guess and annotation:
            return 'false_negative'
        if guess and not annotation:
            return 'false_positive'


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Annotator, self).join(timeout)
