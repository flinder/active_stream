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

    def __init__(self, tp_queue, stoprequest, kw_queue):
        super(Listener, self).__init__()
        self.tp_queue = tp_queue
        self.stoprequest = stoprequest
        self.keyword_queue = kw_queue

    def on_status(self, status):
        logging.info("Received status form streaming API")
        status = self.filter_status(status) 
        if status is None:
            logging.info("Removed by user filter")
            return True
        else:
            status = self.amend_status(status)
            self.tp_queue.put(status)
            return True

    def on_error(self, status):
        return False

    def amend_status(self, status):
        '''
        Adds relevance and default prob relevant to status.
        '''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        status['probability_relevant'] = None
        status['annotation_priority'] = 0

        return status

    def filter_status(self, status):
        '''
        Additional filters to remove statuses. Also converts tweepy Status
        object to dictionary.
        '''
        status = status._json
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
    name: str, name of the thread.
    kw_queue: queue for adding keywords
    '''
    def __init__(self, keywords, credentials, tp_queue, filter_params, 
                 kw_queue, name=None):
        super(Streamer, self).__init__(name=name)
        self.tp_queue = tp_queue
        self.stoprequest = threading.Event()
        self.filter_params = filter_params
        self.keyword_queue = kw_queue
        self.keywords = set(keywords)
        # Set up twitter authentication
        auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                   credentials['consumer_secret'])
        auth.set_access_token(credentials['access_token'],
                              credentials['access_token_secret'])
        self.stream = tweepy.Stream(auth=auth,
                                    listener=Listener(tp_queue, 
                                                      self.stoprequest,
                                                      self.keyword_queue))

    def run(self):
        while not self.stoprequest.isSet():
            logging.info('Ready!')
            logging.info(f'Tracking: {self.keywords}')
            stream_ok = self.stream.filter(track=self.keywords, 
                                           **self.filter_params, async=True)

            while True:
                if self.stoprequest.isSet():
                    self.stream.disconnect()
                    break
                if not self.keyword_queue.empty():
                    logging.info('Found new item in keyword queue')
                    # Check if add or remove
                    request = self.keyword_queue.get()
                    word = request['word']
                    if request['add']:
                        logging.info(f'Adding new keyword to stream: {word}')
                        self.keywords.update([word])
                        self.stream.disconnect()
                    else:
                        logging.info(f'Removing keyword from stream: {word}')
                        self.keywords.remove(word)
                        self.stream.disconnect()
                    break
                time.sleep(0.5)

        logging.info('Leaving stream')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Streamer, self).join(timeout)

