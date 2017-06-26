import tweepy
import threading
import logging
import time
import json

import numpy as np


class Listener(tweepy.StreamListener):
    '''
    Tweepy stream listener

    Grabs statuses from the Twitter streaming API, adds fields required for the
    application, filters irrelevant ones and passes them to the text processor.

    Arguments:
    tp_queue: Text processor queue 
    '''

    def __init__(self, tp_queue, stoprequest, kw_queue, limit_queue):
        super(Listener, self).__init__()
        self.tp_queue = tp_queue
        self.stoprequest = stoprequest
        self.keyword_queue = kw_queue
        self.limit_queue = limit_queue

    def on_data(self, data):
        logging.info('Received data')
        doc = json.loads(data.strip('\n'))
        if 'limit' in doc:
            logging.info('Is limit message')
            self.limit_queue.put(doc)
            return True
        if 'delete' in doc:
            logging.info('Is delete message')
            return True

        logging.info('Is status')
        status = self.filter_status(doc)
        if status is None:
            logging.info("Removed by user filter")
            return True
        else:
            status = self.amend_status(status)
            self.tp_queue.put(status)
            return True

    def on_error(self, status):
        print(status)
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
                 kw_queue, limit_queue, name=None):
        super(Streamer, self).__init__(name=name)
        self.tp_queue = tp_queue
        self.stoprequest = threading.Event()
        self.filter_params = filter_params
        self.keyword_queue = kw_queue
        self.keywords = set(keywords)
        # Set up twitter authentication
        self.auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                        credentials['consumer_secret'])
        self.auth.set_access_token(credentials['access_token'],
                                   credentials['access_token_secret'])
        self.limit_queue = limit_queue
    def run(self):
        
        while not self.stoprequest.isSet():
            logging.info('Ready!')
            logging.info(f'Tracking: {self.keywords}')
            time.sleep(0.05)
            lis = Listener(self.tp_queue, self.stoprequest, self.keyword_queue,
                           self.limit_queue)
            stream = tweepy.Stream(auth=self.auth, listener=lis)
            stream.filter(track=list(self.keywords), **self.filter_params, 
                          async=True)

            while True:
                if self.stoprequest.isSet():
                    stream.disconnect()
                    break
                if not self.keyword_queue.empty():
                    # Check if add or remove
                    request = self.keyword_queue.get()
                    word = request['word']
                    if request['add']:
                        logging.info(f'Adding new keyword to stream: {word}')
                        self.keywords.update([word])
                        stream.disconnect()
                    else:
                        logging.info(f'Removing keyword from stream: {word}')
                        self.keywords.remove(word)
                        stream.disconnect()
                    break

                time.sleep(0.05)

        logging.info('Leaving stream')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Streamer, self).join(timeout)

