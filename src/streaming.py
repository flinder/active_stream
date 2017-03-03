import tweepy
import threading
import logging
import time

import numpy as np


class Listener(tweepy.StreamListener):
    '''
    Tweepy stream listener

    Grabs statuses from the Twitter streaming API, adds fields required for the
    application, filters irrelevant ones and passes them to the text processor.

    Arguments:
    tp_queue: Text processor queue 
    '''

    def __init__(self, tp_queue):
        super(Listener, self).__init__()
        self.tp_queue = tp_queue

    def on_status(self, status):
        logging.debug('Received status')

        status = self.filter_status(status) 
        if status is None:
            logging.debug('Status removed by filter')
            return True
        else:
            status = self.amend_status(status)
            logging.debug('Sending status to text processor')
            self.tp_queue.put(status)
            return True

    def on_error(self, status):
        raise ValueError('Twitter API Exception: {}'.format(status))

    def amend_status(self, status):
        '''
        Adds relevance and default prob relevant to status.
        '''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        status['probability_relevant'] = None
        status['to_annotate'] = False

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
    --------------
    keyword_monitor: dict, containing all keywords as `Keyword()` objects
    credentials: dict, containing Twitter API credentials.
    tp_queue: Queue for the text processor
    offline: bool, if set to true, no tweets from the API are grabbed but fake
        tweets are vreated instead. For testing and developing offline.
    name: str, name of the thread.
    '''
    def __init__(self, keyword_monitor, credentials, tp_queue, name=None, 
                 offline=False):

        logging.debug('Initializing Streamer...')

        super(Streamer, self).__init__(name=name)

        self.offline = offline
        self.tp_queue = tp_queue
        self.stoprequest = threading.Event()

        if not self.offline:
            self.keyword_monitor = keyword_monitor
            # Set up twitter authentication
            auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                       credentials['consumer_secret'])
            auth.set_access_token(credentials['access_token'],
                                  credentials['access_token_secret'])
            self.stream = tweepy.Stream(auth=auth,
                                        listener=Listener(tp_queue))
        else:
            # Get some random text to create tweets when not connected to API
            with open('data/text.txt') as infile:
                text = infile.read().split('\n\n')
                text = [t.replace('\n', ' ') for t in text]
            self.text = text
                
        logging.debug('Success.')


    def run(self):
        logging.debug('Running.')
        if not self.offline:
            keywords = [str(self.keyword_monitor[kw]) for kw in self.keyword_monitor]
            logging.debug('Tracking: {}'.format(keywords))
        stream_ok = True
        while not self.stoprequest.isSet() and stream_ok:
            if not self.offline:
                stream_ok = self.stream.filter(track=keywords)
            else:
                stream_ok = self.generate_tweet()
                time.sleep(np.random.uniform(0, 10, 1))

        logging.debug('Terminating')

    def join(self, timeout=None):
        self.stoprequest.set()
        self.stream.disconnect()
        super(Streamer, self).join(timeout)


    def generate_tweet(self):
        '''
        Generate a test tweet.
        '''
        i = int(np.random.choice(int(len(self.text)), 1))
        t = self.text[i]
        del self.text[i]
        if len(t) > 144:
            t = t[:144]
        status = {'text': t, 'id': i}
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        status['probability_relevant'] = None
        self.tp_queue.put(status)
        logging.debug('Created Random Tweet')
        return True

