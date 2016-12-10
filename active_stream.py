import tweepy
import queue
import threading
import time
import numpy as np
import spacy
import logging
import sys

from pprint import pprint
from sklearn.linear_model import LogisticRegression

# Custom imports
from streaming import Streamer, Listener
from classification import Classifier, Trainer
from annotation import Annotator
from credentials import credentials
from text_processing import TextProcessor
from keywords import Keyword

if __name__ == "__main__":

    # Set global constants 
    BUF_SIZE = 1000

    # Set global variables
    ONE_POSITIVE = False
    ONE_NEGATIVE = False
    RUN_TRAINER = False

    # Set up data structures
    text_processing_queue = queue.Queue(BUF_SIZE)
    classifier_queue = queue.Queue(BUF_SIZE)
    annotation_queue = queue.Queue(BUF_SIZE)
    model_queue = queue.Queue(1)
    kw_queue = queue.Queue(BUF_SIZE)
    keyword_monitor = {}
    dummy_database = []

    # Seed input
    seed = Keyword('merkel', user_word=True)
    keyword_monitor[str(seed)] = seed

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s (%(threadName)s) %(message)s',
                        filename='debug.log')
    
    # Initialize Threads
    streamer = Streamer(name='Streamer', keyword_monitor=keyword_monitor,
                        credentials=credentials['coll_1'])
    text_processor = TextProcessor(name='Text Processor',
                                   queue=text_processing_queue)
    classifier = Classifier(name='Classifier', queue=classifier_queue)
    annotator = Annotator(name='Annotator', queue=annotation_queue)
    trainer = Trainer(name='Trainer', clf=LogisticRegression(),
                      queue=model_queue)
    
    # Start Threads
    try:
        streamer.start()
        text_processor.start()
        classifier.start()
        annotator.start()
        trainer.start()
    except KeyboardInterrupt:
        streamer.stop()
        text_processor.stop()
        classifier.stop()
        annotator.stop()
        trainer.stop()


