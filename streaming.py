import tweepy
import threading
import logging
import time

import numpy as np



class Listener(tweepy.StreamListener):


    def __init__(self, queues):
        super(Listener, self).__init__()
        self.queues = queues

    def on_status(self, status):
        logging.debug('Received status')
        status = self.filter_status(status) 
        if status is None:
            return True
        else:
            status = self.amend_status(status)
            self.queues['text_processor'].put(status)
            return True

    def on_error(self, status):
        raise ValueError('Twitter API Exception: {}'.format(status))

    def amend_status(self, status):
        '''
        Adds relevance fields to status.
        '''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        return status

    def filter_status(self, status):
        '''
        Additional filters to remove statuses. Also converts tweepy Status
        object to dictionary.
        '''
        status = status._json 
        if status['lang'] != 'en':
            return None
        else:
            return status


class Streamer(threading.Thread):
    '''
    Connects to Twitter API and directs incoming statuses to the respective 
    queues.

    Arguments:
    ---------
    keyword_monitor: dict,
    credentials: dict,
    queues: dict,
    offline: bool
    '''
    def __init__(self, keyword_monitor, credentials, queues, group=None, 
            target=None, name=None, args=(), kwargs=None, verbose=None, 
            offline=False):

        logging.debug('Initializing Streamer...')

        super(Streamer, self).__init__(name=name)

        self.offline = offline
        self.queues = queues

        if not self.offline:
            self.keyword_monitor = keyword_monitor
            # Set up twitter authentication
            auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                       credentials['consumer_secret'])
            auth.set_access_token(credentials['access_token'],
                                  credentials['access_token_secret'])
            self.stream = tweepy.Stream(auth=auth,
                                        listener=Listener(queues))
        else:
            # Get some random text to create tweets when not connected to API
            with open('text.txt') as infile:
                text = infile.read().split('\n\n')
                text = [t.replace('\n', ' ') for t in text]
            self.text = text
                

        logging.debug('Success.')
    def run(self):
        logging.debug('Running.')
        if not self.offline:
            keywords = [str(self.keyword_monitor[kw]) for kw in self.keyword_monitor]
            logging.debug('Tracking: {}'.format(keywords))
        while True:
            if not self.offline:
                try:
                    ok = self.stream.filter(track=keywords)
                except KeyboardInterrupt:
                    self.stream.disconnect()
                    break
            else:
                ok = self.generate_tweet()
                time.sleep(np.random.uniform(0, 10, 1))


    def generate_tweet(self):
        i = np.random.choice(len(self.text), 1)        
        t = self.text[i]
        if len(t) > 144:
            t = t[:144]
        status = {'text': t}
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        self.queues['text_processor'].put(status)
        logging.debug('Created Random Tweet')
        return True


