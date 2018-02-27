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
    stoprequest: Threading.Event, used to stop the thread
    data: all data structures. See app.py for details
    '''


    def __init__(self, stoprequest, data):
        super(Listener, self).__init__()
        self.tp_queue = data['queues']['text_processing']
        self.stoprequest = stoprequest
        self.keyword_queue = data['queues']['keywords']
        self.limit_queue = data['queues']['limit']
        self.message_queue = data['queues']['messages']

    def on_data(self, data):
        doc = json.loads(data.strip('\n'))
        if 'limit' in doc:
            logging.debug('Received limit message')
            self.limit_queue.put(doc)
            return True
        if 'delete' in doc:
            logging.debug('Received delete message')
            return True
        
        logging.debug('Received status')
        status = self.filter_status(doc)
        if status is None:
            logging.debug('Status removed by filter')
            return True
        else:
            status = self.amend_status(status)
            self.tp_queue.put(status)
            logging.debug('Status sent to text processor')
            return True

    def on_error(self, status):
        logging.error(f'Received error message from API: {status}')
        self.message_queue.put(f'Received error message form Twitter API: {status}')
        return False

    def amend_status(self, status):
        '''
        Adds relevance and default prob relevant to status.
        '''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        status['probability_relevant'] = None
        status['annotation_priority'] = 0
        status['clf_version'] = -1

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
    data: All data structures. See app.py for details
    name: str, name of the thread.
    '''
    def __init__(self, credentials, data):
        super(Streamer, self).__init__(name='Streamer')
        self.data = data
        self.text_processing_queue = data['queues']['text_processing']
        self.stoprequest = threading.Event()
        self.filter_params = data['filters']
        self.keyword_queue = data['queues']['keywords']
        self.keywords = set()
        self.auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                        credentials['consumer_secret'])
        self.auth.set_access_token(credentials['access_token'],
                                   credentials['access_token_secret'])
        self.limit_queue = data['queues']['limit']
        self.message_queue = data['queues']['messages']
        self.last_connection = 0
        self.min_reconnect_pause = 20

    def run(self):
        
        while not self.stoprequest.isSet():
            logging.debug('Ready!')
            time.sleep(0.05)

            if len(self.keywords) > 0:
                logging.info(f'Tracking: {self.keywords}')
                lis = Listener(self.stoprequest, self.data)
                self.last_connection = time.time()
                stream = tweepy.Stream(auth=self.auth, listener=lis)
                stream.filter(track=list(self.keywords), **self.filter_params, 
                              async=True)
                self.last_connection = time.time()

            while True:
                if self.stoprequest.isSet():
                    try:
                        stream.disconnect()
                    except UnboundLocalError:
                        pass
                    break
                
                # Get all new additions / deletions
                if not self.keyword_queue.empty():
                    requests = []
                    while not self.keyword_queue.empty():
                        requests.append(self.keyword_queue.get())
                    
                    # Get consolidated list
                    for request in requests:
                        word = request['word']
                        if request['add']:
                            self.keywords.update([word])
                        else:
                            self.keywords.remove(word)

                    # Disconnect stream and break to jump to reconnect
                    try:
                        stream.disconnect()
                    except UnboundLocalError:
                        pass
                    self.message_queue.put('Keyword changes applied!')
                    break
                
                time_since = time.time() - self.last_connection
                if time_since < self.min_reconnect_pause:
                    time.sleep(self.min_reconnect_pause - time_since)
                else:
                    time.sleep(0.1)

        logging.debug('Leaving stream')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Streamer, self).join(timeout)

