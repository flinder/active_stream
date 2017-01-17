import threading
import logging
import signal

import shared

class Annotator(threading.Thread):
    '''
    Handles manual annotations.

    Takes statuses from queues['annotator'], presents and presents them to the
    user. Once user input is received updates `ONE_POSITIVE` and `ONE_NEGATIVE`
    (if the first negative / positive annotation) and sets `RUN_TRAINER` to True
    (which triggers the Trainer Thread to re-train the model if `ONE_POSITIVE`
    and `ONE_NEGATIVE` are both `True`).

    Arguments:
    ---------------  
    queues: dict containing queues to pass data between threads. Each queue must
        be of class `queue.Queue`.
    name: str, name of the thread.
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, queues, name=None):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.queues = queues
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        while not shared.TERMINATE:
            if not self.queues['annotator'].empty():
                status = self.queues['annotator'].get()
                while not shared.TERMINATE:
                    print(status['text'])
                    annotation = input('Relevant? (y/n)')
                    if annotation == 'y':
                        status['manual_relevant'] = True
                        shared.ONE_POSITIVE = True
                        shared.RUN_TRAINER = True 
                        break
                    elif annotation == 'n':
                        status['manual_relevant'] = False
                        shared.ONE_NEGATIVE = True
                        shared.RUN_TRAINER = True
                        break
                    else:
                        continue
                self.queues['database'].update({'id': status['id']}, status,
                                               upsert=True)
        # Run cleanup if terminated
        logging.debug('Terminating')
        self.cleanup()

    def cleanup(self):
        return None

