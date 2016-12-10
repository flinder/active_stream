import threading
import logging

class KWManagerThread(threading.Thread):
    '''
    Takes batches of incoming statuses and suggests new keywords based on
    co-occurence with existing (high quality) keywords. Also monitors keywords
    and controls activation / deactivation

    # NOT IMPLEMENTED YET
    '''
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Annotator...')
        super(KWExpanderThread, self).__init__()
        logging.debug('Success.')

    def get_all(q, n_items):
        items = []
        for i in range(0, n_items):
            try:
                items.append(q.get_nowait())
            except Empty:
                break
        return items 

    def run(self):
        global keyword_monitor
        global seed
        global BUF_SIZE

        logging.debug('Running...')

        # Activate seed keywords
        keyword_monitor[str(seed)] = seed
        seed.activate()

        while True:
            # Check incoming tweets and update keyword performance
            if not kw_queue.empty():
                all_new = get_all(kw_queue, BUF_SIZE)
            
            # [Store tokenized tweet text with Text Processor]

            # Assess keyword performance and deactivate if necessary
            

            # Propose new keywords 
            pass


class Keyword(object):
    '''
    Keyword to track with Twitter API
    '''    

    def __init__(self, word, user_word=False):
        self.word = word
        self.n_relevant = 0
        self.n_irrelevant = 0
        self.active = False
        self.history = []
        self.user_word = user_word

    def  __str__(self):
        return self.word

    def activate(self):
        self.active = True
        self.history.append(('activated', time.time()))

    def deactivate(self):
        self.active = False
        self.history.append(('deactivated', time.time()))

   


