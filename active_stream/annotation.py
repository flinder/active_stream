import threading
import logging
import queue
import pymongo

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
    name: str, name of the thread.
    train_threshold: int, number of annotations (for each class) before training
        starts.
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, database, train_event, annotation_response, socket, 
                 name=None, train_threshold=1):
        super(Annotator, self).__init__(name=name)
        self.database = database
        self.train = train_event
        self.stoprequest = threading.Event()
        self.n_positive = False
        self.n_negative = False
        self.train_threshold = train_threshold
        self.annotation_response = annotation_response
        self.socket = socket
        self.annotated_text = {}
        self.n_trainer_triggered = 0

    def run(self):
        logging.info('Ready!')
        first = True
        while not self.stoprequest.isSet():

            # Look for work:
            not_annotated = self.database.find({'manual_relevant': None,
                                                'probability_relevant': {
                                                    '$ne': None
                                                    }})
            
            # If no work, wait and try again
            if not_annotated.count() == 0:
                if first:
                    self.socket.emit('display_tweet', {'tweet_id': 'waiting'})
                    first = False
                sleep(0.1)
                continue

            work = not_annotated.sort('annotation_priority', 
                                       pymongo.ASCENDING).limit(1)
            first = True
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
                    self.socket.emit('display_tweet', {'tweet_id': id_,
                                                       'guess': guess})
                
                while True:
                    try:
                        response = self.annotation_response.get(timeout=0.1)
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
                    continue
                elif response == 'refresh':
                    continue
                    
                else:
                    raise ValueError('Received invalid response from interface')

                # Store the text in memory to not ask twice
                self.annotated_text[status['text']] = out

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

                
        logging.info('Stopped')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Annotator, self).join(timeout)
