import threading
import logging
import queue
import numpy as np

from time import sleep

class Monitor(threading.Thread):
    '''
    Monitor basic data collection stats    

    Arguments:
    ---------------  
    database: pymongo connection
    socket: websocket for client communication
    mif_queue: Queue to receive most important features from trainer
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, database, socket, most_important_features, stream, 
                 limit_queue, clf, name=None):
        super(Monitor, self).__init__(name=name)
        self.database = database
        self.stoprequest = threading.Event()
        self.socket = socket
        self.mif_queue = most_important_features
        self.limit_queue = limit_queue
        self.mif = None
        self.streamer = stream
        self.last_count = 0
        self.clf = clf
        self.counts = []
        self.missed = 0
    
    def run(self):
        logging.info('Ready!')
        while not self.stoprequest.isSet():
            self.socket.emit('db_report', {'data': self.get_stats()})
            sleep(1)
        logging.info('Stopped')

    def get_stats(self):

        d = self.database
        n_total = d.count()
        
        # Calculate average per second rate for last minute
        self.counts.append(n_total)
        n_counts = len(self.counts)
        if n_counts > 1:
            avg_rate = round(np.mean(np.diff(np.array(self.counts))), 1)
        else:
            avg_rate = np.nan

        if n_counts > 60:
            diff = n_counts - 60
            del self.counts[:diff]
            
        # Get number of missed tweets
        if not self.limit_queue.empty():
            msg = self.limit_queue.get()
            self.missed += msg['limit']['track']
        if not self.mif_queue.empty():
            self.mif = self.mif_queue.get()
            
        n_annotated = d.count({'manual_relevant': {'$ne': None}})
        current_clf_version = self.clf.clf_version
        n_classified = d.count({'probability_relevant': {'$ne': None},
                                'clf_version': {'$gte': current_clf_version}})
        try:
            #perc_classified = round(n_classified / n_total, 1)
            perc_classified = round((n_classified*100) / n_total, 1)
        except ZeroDivisionError:
            perc_classified = 0
        
        if current_clf_version > 0:
            training_started = True
        else:
            training_started = False

        return {'total_count': n_total,
                'rate': avg_rate,
                'missed': self.missed,
                'annotated': n_annotated,
                'classified': perc_classified,
                'training_started': training_started,
                'suggested_features': self.mif}

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Monitor, self).join(timeout)
