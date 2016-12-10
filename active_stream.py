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

    # Get authentication data
    consumer_key = credentials['coll_1']['consumer_key']
    consumer_secret = credentials['coll_1']['consumer_secret']
    access_token = credentials['coll_1']['access_token']
    access_token_secret = credentials['coll_1']['access_token_secret']
    
    # Set up authentication
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

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

    # Set up stream
    listener = Listener()
    stream = tweepy.Stream(auth=auth, listener=listener)

    # Seed input
    seed = Keyword('merkel', user_word=True)
    keyword_monitor[str(seed)] = seed

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s (%(threadName)s) %(message)s',
                        filename='debug.log')
    
    # Initialize Threads
    streamer = Streamer(name='Streamer')
    text_processor = TextProcessor(name='Text Processor')
    classifier = Classifier(name='Classifier')
    annotator = Annotator(name='Annotator')
    trainer = Trainer(name='Trainer', clf=LogisticRegression())
    
    # Start Threads
    streamer.start()
    text_processor.start()
    classifier.start()
    annotator.start()
    trainer.start()


