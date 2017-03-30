# Script to run the active_stream application. Set all parameters in 'config'
# section 
import queue
import logging
import sys
import time 
import threading

from pymongo import MongoClient
from sklearn.linear_model import SGDClassifier
from gensim import corpora

# Custom imports
sys.path.append('src/')
from streaming import Streamer, Listener 
from classification import Classifier, Trainer
from annotation import Annotator
from credentials import credentials
from text_processing import TextProcessor
from keywords import Keyword


def main():
    # Start Threads
    for thread in threads:
        thread.start()
    
    # Wait for termination
    try:
        while True:
            time.sleep(0.05)
    except KeyboardInterrupt:
        logging.debug('Keyboard Interrupt. Attempting to terminate all threads...')
        for thread in threads:
            thread.join()

        raise KeyboardInterrupt from None



if __name__ == "__main__":
   
    # =========================================================================== 
    # Config
    # =========================================================================== 
    no_api = False                # Set to True if no API connection available
                                  # in this case fake 'tweets' are generated
    keywords = ['merkel']         # Seed keywords
    BUF_SIZE = 100                # Buffer size of queues
    db = 'active_stream'          # Mongo Database name
    collection = 'dump'           # Mongo db collection name
    # =========================================================================== 
    
    # Set up data structures
    text_processor_queue = queue.Queue(BUF_SIZE)
    db = MongoClient()[db][collection]
    model_queue = queue.Queue(1)
    te = threading.Event() # train event (triggers model training in annotator)
    dl = threading.Lock()  
    d = corpora.Dictionary()

    # Clear database
    db.drop()

    # Process seed input
    keyword_monitor = {}
    for kw in keywords:
        seed = Keyword(kw, user_word=True)
        keyword_monitor[str(seed)] = seed

    # Set up logging
    with open('debug.log', 'w') as logfile:
        pass
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s (%(threadName)s) %(message)s',
                        filename='debug.log')
    
    # Initialize Threads
    streamer = Streamer(name='Streamer', keyword_monitor=keyword_monitor,
                        credentials=credentials['coll_1'], 
                        tp_queue=text_processor_queue, offline=no_api)
    text_processor = TextProcessor(name='Text Processor', database=db,
                                   tp_queue=text_processor_queue, 
                                   dictionary=d, dict_lock=dl)
    classifier = Classifier(name='Classifier', database=db, model=model_queue,
                            dictionary=d, dict_lock=dl)
   
    annotator = Annotator(name='Annotator', database=db, train_event=te)
    trainer = Trainer(name='Trainer', 
                      clf=SGDClassifier(loss='log', penalty='elasticnet'), 
                      database=db, model=model_queue, train_trigger=te,
                      dictionary=d, dict_lock=dl)
    
    threads = [streamer, text_processor, classifier, annotator, trainer]
    
    # Run app
    main()
