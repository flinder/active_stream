# Script to run the active_stream application. Set all parameters in 'config'
# section

import queue
import logging
import sys

from pymongo import MongoClient
from sklearn.linear_model import LogisticRegression

# Custom imports
sys.path.append('src/')
from streaming import Streamer, Listener
from classification import Classifier, Trainer
from annotation import Annotator
from credentials import credentials
from text_processing import TextProcessor
from keywords import Keyword
import shared


def main(threads):
    # Start Threads
    for thread in threads:
        thread.start()
    
    # Wait for termination
    while True:
        try:
            pass
        except Exception as e:
            shared.TERMINATE = True
            # Wait until every thread's cleanup procedure is done
            for thread in threads:
                thread.join()

            raise e

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
    qs = {'text_processor': queue.Queue(BUF_SIZE),
          'classifier': queue.Queue(BUF_SIZE),
          'annotator': queue.Queue(BUF_SIZE),
          'model': queue.Queue(1),
          'database': MongoClient()[db][collection]
          }

    # Process seed input
    keyword_monitor = {}
    for kw in keywords:
        seed = Keyword('merkel', user_word=True)
        keyword_monitor[str(seed)] = seed

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s (%(threadName)s) %(message)s',
                        filename='debug.log')
    
    # Initialize Threads
    streamer = Streamer(name='Streamer', keyword_monitor=keyword_monitor,
                        credentials=credentials['coll_1'], queues=qs, 
                        offline=no_api)
    text_processor = TextProcessor(name='Text Processor', queues=qs)
    classifier = Classifier(name='Classifier', queues=qs)
   
    annotator = Annotator(name='Annotator', queues=qs)
    trainer = Trainer(name='Trainer', clf=LogisticRegression(), queues=qs)
    
    threads = [streamer, text_processor, classifier, annotator, trainer]
    
    # Run
    main(threads)   
