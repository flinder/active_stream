import threading
import logging

import shared

class Annotator(threading.Thread):
    '''
    Handles manual annotations.
    '''

    def __init__(self, queues, group=None, target=None, name=None, args=(), 
            kwargs=None, verbose=None):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.queues = queues
        logging.debug('Success.')

    def run(self):

        logging.debug('Running.')
        while True:
            if not self.queues['annotator'].empty():
                status = self.queues['annotator'].get()
                while True:
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
                shared.database_lock.acquire()
                shared.database.append(status)
                shared.database_lock.notify_all()
                shared.database_lock.release()


