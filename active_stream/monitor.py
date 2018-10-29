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
    data: datastructures, see app.py for details
    streamer: threading.Thread
    classifier: threading.Thread
    annotator: threading.Thread
    
    Methods:
    ---------------  
    run

    '''

    def __init__(self, data, streamer, classifier, annotator):
        super(Monitor, self).__init__(name='Monitor')
        self.database = data['database']
        self.stoprequest = threading.Event()
        self.socket = data['socket']
        self.mif_queue = data['queues']['most_important_features']
        self.limit_queue = data['queues']['limit']
        self.mif = None
        self.streamer = streamer
        self.last_count = 0
        self.clf = classifier
        self.annotator = annotator
        self.counts = []
        self.missed = 0
        self.message_queue = data['queues']['messages']
        self.report_interval = 0.3
    
    def run(self):
        logging.debug('Ready!')
        while not self.stoprequest.isSet():
            self.socket.emit('db_report', {'data': self.get_stats()})
            sleep(self.report_interval)
        logging.debug('Stopped')

    def get_stats(self):

        d = self.database
        n_total = d.count({'sample': 'track'})
        n_sample = d.count({'sample': 'sample'})
        
        # Calculate average per second rate for last minute
        self.counts.append(n_total)
        n_counts = len(self.counts)
        if n_counts > 1:
            avg_rate = round(np.mean(
                np.diff(np.array(self.counts))), 1) * 1/self.report_interval
        else:
            avg_rate = np.nan

        if n_counts > 5:
            diff = n_counts - 5
            del self.counts[:diff]
            
        # Get number of missed tweets
        while not self.limit_queue.empty():
            msg = self.limit_queue.get()
            self.missed += msg['limit']['track']
        if not self.mif_queue.empty():
            self.mif = self.mif_queue.get()
            
        n_annotated = d.count({'manual_relevant': {'$ne': None}, 
                               'sample': 'track'})
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
        
        # Get all new messages
        messages = []
        while not self.message_queue.empty():
            messages.append(self.message_queue.get())
        
        metrics = self.get_clf_metrics()
        return {'total_count': n_total,
                'rate': avg_rate,
                'missed': self.missed,
                'annotated': n_annotated,
                'classified': perc_classified,
                'training_started': training_started,
                'suggested_features': self.mif,
                'f1': metrics['f1_score'],
                'precision': metrics['precision'],
                'recall': metrics['recall'],
                'messages': messages,
                'clf_version': current_clf_version
                }

    def get_clf_metrics(self):
        performance = self.annotator.clf_performance
        tp = performance['true_positive']
        fp = performance['false_positive']
        fn = performance['false_negative']
        tn = performance['true_negative']
        out = {'precision': 'NA', 'recall': 'NA', 'f1_score': 'NA'}
        if tp == 0 and fp == 0:
            return out
        if tp == 0 and fn == 0:
            return out
        out['precision'] = round(tp / (tp + fp), 1)
        out['recall'] = round(tp / (tp + fn), 1)
        out['f1_score'] = round((2*tp) / (2*tp + fn + fp), 1)

        return out


    def join(self, timeout=None):
        self.stoprequest.set()
        super(Monitor, self).join(timeout)
