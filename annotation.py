import threading
import logging



class Annotator(threading.Thread):
    '''
    Handles manual annotations.
    '''

    def __init__(self, queue, group=None, target=None, name=None, args=(), 
            kwargs=None, verbose=None):
        logging.debug('Initializing Annotator...')
        super(Annotator, self).__init__(name=name)
        self.queue = queue
        logging.debug('Success.')

    def run(self):
        global ONE_POSITIVE
        global ONE_NEGATIVE
        global RUN_TRAINER

        logging.debug('Running.')
        while True:
            if not self.queue.empty():
                status = self.queue.get()
                while True:
                    print(status['text'])
                    annotation = input('Relevant? (y/n)')
                    if annotation == 'y':
                        status['manual_relevant'] = True
                        ONE_POSITIVE = True
                        RUN_TRAINER = True 
                        break
                    elif annotation == 'n':
                        status['manual_relevant'] = False
                        ONE_NEGATIVE = True
                        RUN_TRAINER = True
                        break
                    else:
                        continue
                dummy_database.append(status)


