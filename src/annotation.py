import threading
import logging
import queue

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

    def __init__(self, database, train_event, name=None, train_threshold=10):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.database = database
        self.train = train_event
        self.stoprequest = threading.Event()
        self.n_positive = False
        self.n_negative = False
        self.train_threshold = train_threshold
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        while not self.stoprequest.isSet():

            # Look for work:
            work = self.database.find({'manual_relevant': None,
                                       'to_annotate': True}).limit(1)

            #if work.count() == 0:
            #    work = self.database.find({
            #        'manual_relevant': None,
            #        'probability_relevant': {'$ne': None}}).limit(1)

            if work.count() > 0:
                for status in work:
                    if self.stoprequest.isSet():
                        break
                    print(status['text'])
                    print(status['probability_relevant'])
                    while not self.stoprequest.isSet():
                        annotation = input('Relevant? (y/n)')
                        if annotation == 'y':
                            out = True
                            self.n_positive += 1
                            break
                        elif annotation == 'n':
                            out = False
                            self.n_negative += 1
                            break
                        else:
                            continue
                    if self.stoprequest.isSet():
                        break
                    # Update record in DB
                    msg = self.database.update({'_id': status['_id']}, 
                                               {'$set': {'manual_relevant': out,
                                                         'to_annotate': False,
                                                         'probability_relevant': int(out)}})

                    # Trigger trainer if necessary
                    if (self.n_positive >= self.train_threshold
                        and self.n_negative >= self.train_threshold):
                        self.train.set()
            else:
                sleep(0.05)
                
                    
        logging.debug('Terminating')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Annotator, self).join(timeout)
