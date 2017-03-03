import threading
import logging
import queue

from time import sleep

class Annotator(threading.Thread):
    '''
    Handles manual annotations.

    Queries database for uncertain statuses, presents and presents them to the
    user. Once user input is received updates `ONE_POSITIVE` and `ONE_NEGATIVE`
    (if the first negative / positive annotation) and sets `RUN_TRAINER` to True
    (which triggers the Trainer Thread to re-train the model if `ONE_POSITIVE`
    and `ONE_NEGATIVE` are both `True`).

    Arguments:
    ---------------  
    database: pymongo connection
    train_event: threading event. To communicate with Trainer
    name: str, name of the thread.
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, database, train_event, name=None):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.database = database
        self.train = train_event
        self.stoprequest = threading.Event()
        self.one_positive = False
        self.one_negative = False
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        while not self.stoprequest.isSet():

            # Look for work:
            work = self.database.find({'manual_relevant': None,
                                       'to_annotate': True}).limit(1)

            if work.count() == 0:
                work = self.database.find({
                    'manual_relevant': None,
                    'probability_relevant': {'$ne': None}}).limit(1)

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
                            self.one_positive = True
                            break
                        elif annotation == 'n':
                            out = False
                            self.one_negative = True
                            break
                        else:
                            continue
                    if self.stoprequest.isSet():
                        break
                    # Update record in DB
                    msg = self.database.update({'_id': status['_id']}, 
                                               {'$set': {'manual_relevant': out}})
                    logging.debug('DB operation: {}'.format(msg))

                    # Trigger trainer if necessary
                    if self.one_positive and self.one_negative:
                        self.train.set()
            else:
                sleep(0.05)
                
                    
        logging.debug('Terminating')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Annotator, self).join(timeout)
