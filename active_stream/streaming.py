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
    data: all data structures. See app.py for details
    '''


    def __init__(self, data):
        super(Listener, self).__init__()
        self.tp_queue = data['queues']['text_processing']
        self.keyword_queue = data['queues']['keywords']
        self.limit_queue = data['queues']['limit']
        self.message_queue = data['queues']['messages']

    def on_data(self, data):
        doc = json.loads(data.strip('\n'))
        if 'limit' in doc:
            self.limit_queue.put(doc)
            return True
        if 'delete' in doc:
            return True
        
        status = self.filter_status(doc)
        if status is None:
            return True
        else:
            status = self.amend_status(status)
            self.tp_queue.put(status)
            return True

    def on_error(self, status):
        logging.error(f'Received error message from API: {status}')
        self.message_queue.put(f'Received error message form Twitter API: {status}')
        return False

    def amend_status(self, status):
        '''Adds relevance and default prob relevant to status.'''
        status['classifier_relevant'] = None
        status['manual_relevant'] = None
        status['probability_relevant'] = None
        status['annotation_priority'] = 0
        status['clf_version'] = -1
        status['sample'] = 'track'

        return status

    def filter_status(self, status):
        '''Additional filters to remove statuses.'''
        try:
            if status['possibly_sensitive']:
                return None
        except KeyError:
            pass
        return status

class SampleListener(Listener):
    def amend_status(self, status):
        '''Adds relevance and default prob relevant to status.'''
        status['classifier_relevant'] = False
        status['manual_relevant'] = False
        status['probability_relevant'] = 0
        status['annotation_priority'] = 0
        status['clf_version'] = -1
        status['sample'] = 'sample'

        return status


class Streamer(threading.Thread):
    '''Connects to Twitter API and directs incoming statuses to the respective 
    queues.

    Arguments:
    --------------
    keyword_monitor: dict, containing all keywords as `Keyword()` objects
    credentials: dict, containing Twitter API credentials.
    data: All data structures. See app.py for details
    name: str, name of the thread.
    '''
    def __init__(self, credentials_track, credentials_sample, data):
        super(Streamer, self).__init__(name='Streamer')
        self.data = data
        self.text_processing_queue = data['queues']['text_processing']
        self.stoprequest = threading.Event()
        self.filter_params = data['filters']
        self.keyword_queue = data['queues']['keywords']
        self.keywords = set()
        self.auth_track = tweepy.OAuthHandler(credentials_track['consumer_key'], 
                                        credentials_track['consumer_secret'])
        self.auth_track.set_access_token(credentials_track['access_token'],
                                   credentials_track['access_token_secret'])
        self.auth_sample = tweepy.OAuthHandler(credentials_sample['consumer_key'], 
                                        credentials_sample['consumer_secret'])
        self.auth_sample.set_access_token(credentials_sample['access_token'],
                                   credentials_sample['access_token_secret'])
        self.limit_queue = data['queues']['limit']
        self.message_queue = data['queues']['messages']
        self.last_connection = 0
        self.min_reconnect_pause = 20

    def run(self):
        logging.debug('Ready!')
        while not self.stoprequest.isSet():
            if len(self.keywords) > 0:
                logging.info(f'Tracking: {self.keywords}')
                lis = Listener(self.data)
                lis_sample = SampleListener(self.data)
                self.last_connection = time.time()
                stream = tweepy.Stream(auth=self.auth_track, 
                                       listener=lis)
                sample_stream = tweepy.Stream(auth=self.auth_sample, 
                                              listener=lis_sample)
                logging.debug('starting track stream')
                stream.filter(track=list(self.keywords), async=True,
                              **self.filter_params)
                logging.debug('starting sample stream')
                sample_stream.sample(async=True, stall_warnings=True, 
                                     **self.filter_params)
                # Python 3.7 will require:
                #stream.filter(track=list(self.keywords), is_async=True,
                #        **self.filter_params)
                logging.debug('done')
                self.last_connection = time.time()

            while True:
                if self.stoprequest.isSet():
                    try:
                        stream.disconnect()
                        sample_stream.disconnect()
                    except UnboundLocalError as e:
                        logging.error(f'Error disconnecting stream: {e}')
                    break
                
                # Get all new additions / deletions
                if not self.keyword_queue.empty():
                    logging.debug('New keywords found in queue')
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
                        logging.error('UnboundLocalError ignored')
                        pass
                    self.message_queue.put('Keyword changes applied!')
                    break
                
                time_since = time.time() - self.last_connection
                if time_since < self.min_reconnect_pause:
                    time.sleep(self.min_reconnect_pause - time_since)
                else:
                    time.sleep(0.5)

        logging.debug('Leaving stream')

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Streamer, self).join(timeout)

