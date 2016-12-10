import tweepy
import threading
import logging


class Listener(tweepy.StreamListener):

    def on_status(self, status):
        status = self.filter_status(status) 
        if status is None:
            return True
        else:
            status = self.amend_status(status)
            text_processor.queue.put(status)
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
    '''
    def __init__(self, keyword_monitor, credentials, group=None, target=None, 
            name=None, args=(), kwargs=None, verbose=None):
        logging.debug('Initializing Streamer...')
        super(Streamer, self).__init__(name=name)
        self.keyword_monitor = keyword_monitor
        # Set up twitter authentication
        auth = tweepy.OAuthHandler(credentials['consumer_key'], 
                                   credentials['consumer_secret'])
        auth.set_access_token(credentials['access_token'],
                              credentials['access_token_secret'])
        self.stream = tweepy.Stream(auth=auth, listener=Listener())
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        self.keyword_monitor
        keywords = [str(self.keyword_monitor[kw]) for kw in self.keyword_monitor]
        logging.debug('Tracking: {}'.format(keywords))
        while True:
            try:
                ok = self.stream.filter(track=keywords)
            except KeyboardInterrupt:
                self.stream.disconnect()
                break



