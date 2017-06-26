import threading
import logging
import queue

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
                 limit_queue, name=None):
        super(Monitor, self).__init__(name=name)
        self.database = database
        self.stoprequest = threading.Event()
        self.socket = socket
        self.mif_queue = most_important_features
        self.limit_queue = limit_queue
        self.mif = None
        self.streamer = stream
        self.last_count = 0
    
    def run(self):
        logging.info('Ready!')
        while not self.stoprequest.isSet():
            stats = self.get_stats()
            if not self.mif_queue.empty():
                self.mif = self.mif_queue.get()
            stats['mif'] = self.mif
            self.socket.emit('db_report', {'data': stats})
            sleep(1)
        
        logging.info('Stopped')

    def get_stats(self):
        d = self.database
        n_total = d.count()
        rate = n_total - self.last_count 
        self.last_count = n_total
        missed = 0
        if not self.limit_queue.empty():
            msg = self.limit_queue.get()
            missed = msg['limit']['track']
            
        n_annotated = d.count({'manual_relevant': {'$ne': None}})
        n_annotated_p = d.count({'manual_relevant': True})
        n_annotated_n = d.count({'manual_relevant': False})

        n_classified = d.count({'probability_relevant': {'$ne': None}})
        n_classified_p = d.count({'classifier_relevant': True})
        n_classified_n = d.count({'classifier_relevant': False})
        
        return {'total_count': n_total,
                'rate': rate,
                'missed': missed}
                #'percentage_annotated': round(n_annotated * 100/ n_total, 3),
                #'n_annotated_+': n_annotated_p,
                #'n_annotated_-': n_annotated_n,
                #'percentage_classified': round(n_classified * 100/ n_total, 3) ,
                #'percentage_classified_+': round(n_classified_p * 100/ n_total, 
                #                                 3),
                #'percentage_classified_-': round(n_classified_n * 100/ n_total, 
                #                                 3),
                #'keywords': list(self.streamer.keywords)
                #}

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Monitor, self).join(timeout)
