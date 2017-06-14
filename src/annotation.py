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

    def __init__(self, database, train_event, display_queue, annotated_queue,
                 name=None, train_threshold=10):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.database = database
        self.train = train_event
        self.stoprequest = threading.Event()
        self.n_positive = False
        self.n_negative = False
        self.train_threshold = train_threshold
        self.display_queue = display_queue
        self.annotated_queue = annotated_queue
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
                logging.debug('New status to annotate. Putting in display queue.')
                for status in work:
                    self.display_queue.put(status['id'])

                logging.debug('Waiting for user input...')
                response = self.annotated_queue.get()
                logging.debug('Received input. Processing...')

                if response == 'Yes':
                    out = True
                    self.n_positive += 1
                elif response == 'No':
                    out = False
                    self.n_negative += 1
                else:
                    logging.error('Received invalid response from interface')

                # Update record in DB
                msg = self.database.update({'_id': status['_id']}, 
                                           {'$set': {'manual_relevant': out,
                                                     'to_annotate': False,
                                                     'probability_relevant': int(out)}})

                # Trigger trainer if necessary
                if (self.n_positive >= self.train_threshold
                    and self.n_negative >= self.train_threshold):
                    logging.debug('Triggering trainer')
                    self.train.set()

            else:
                sleep(0.05)
                
                    
        logging.debug('Terminating')


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Annotator, self).join(timeout)
