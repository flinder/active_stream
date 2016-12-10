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
            text_processing_queue.put(status)
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
    '''
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
            verbose=None):
        logging.debug('Initializing Streamer...')
        super(Streamer, self).__init__(name=name)
        logging.debug('Success.')

    def run(self):
        logging.debug('Running.')
        global keyword_monitor
        keywords = [str(keyword_monitor[kw]) for kw in keyword_monitor]
        logging.debug('Tracking: {}'.format(keywords))
        while True:
            try:
                ok = stream.filter(track=keywords)
            except KeyboardInterrupt:
                stream.disconnect()
                break



