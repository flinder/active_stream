import threading
import logging

from shared import ONE_POSITIVE, ONE_NEGATIVE, RUN_TRAINER, database, database_lock


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

   


