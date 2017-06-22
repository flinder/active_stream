import queue
import logging
import sys
import time 
import threading 
import Stemmer
from pymongo import MongoClient
from sklearn.linear_model import SGDClassifier
from gensim import corpora
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from gevent import monkey; monkey.patch_all()

# Custom imports
sys.path.append('active_stream/')
from streaming import Streamer, Listener 
from annotation import Annotator
from credentials import credentials
from text_processing import TextProcessor
from monitor import Monitor
from classification import Classifier, Trainer

async_mode = "threading"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode, logger=False)
thread = None

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html', async_mode=socketio.async_mode)

@socketio.on('connect')
def connected():
    emit('log', {'data': 'Connected'})

@socketio.on('tweet_relevant')
def tweet_relevant():
    annot_resp.put('relevant')

@socketio.on('tweet_irrelevant')
def tweet_irrelevant():
    annot_resp.put('irrelevant')

@socketio.on('refresh')
def tweet_irrelevant():
    annot_resp.put('refresh')

@socketio.on('skip')
def tweet_irrelevant():
    annot_resp.put('skip')

@socketio.on('connect')
def test_connect():
    logging.info("Starting Annotator.")
    try:
        annotator.start()
    except Exception as e:
        logging.info("Received additional connection. Connecting to exsiting "+
                     "annotator")

@socketio.on('disconnect_request')
def test_disconnect():
    logging.info("Stopping Annotator.")
    annotator.join()

@socketio.on('add_keyword')
def add_keyword(message):
    logging.info('Received request to add new keyword. Sending to Streamer.')
    keyword_queue.put({'add': True, 'word': message['data']})

@socketio.on('remove_keyword')
def add_keyword(message):
    logging.info('Received request to remove keyword. Sending to Streamer.')
    keyword_queue.put({'add': False, 'word': message['data']})

if __name__ == '__main__':

    # =========================================================================== 
    # Config
    # =========================================================================== 
    no_api = False                # Set to True if no API connection available
                                  # in this case fake 'tweets' are generated
    seed_keywords = []        # Seed keywords
    BUF_SIZE = 100                # Buffer size of queues
    db = 'active_stream'          # Mongo Database name
    collection = 'dump'           # Mongo db collection name
    filters = {'languages': ['en'], 'locations': []}
    # =========================================================================== 
    
    # Set up data structures
    text_processor_queue = queue.Queue(BUF_SIZE)
    db = MongoClient()[db][collection]
    model_queue = queue.Queue(1)
    annot_resp = queue.Queue(1)
    te = threading.Event() 
    d = corpora.Dictionary()
    mif = queue.Queue(1)
    keyword_queue = queue.Queue(100)

    # Clear database
    db.drop()

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s (%(threadName)s) %(message)s',
                    filename='debug.log') 

    logging.info('\n'*5)
    logging.info('*'*10 + 'ACTIVE STREAM' + '*'*10)
    logging.info('Starting Application...')

    #for key in logging.Logger.manager.loggerDict:
    #    print(key) 
    #sys.exit()

    # Initialize Threads
    streamer = Streamer(name='Streamer', keywords=seed_keywords,
                        credentials=credentials['coll_1'], 
                        tp_queue=text_processor_queue,  
                        filter_params=filters, kw_queue=keyword_queue)
    text_processor = TextProcessor(name='Text Processor', database=db,
                                   tp_queue=text_processor_queue, 
                                   dictionary=d)
    annotator = Annotator(name='Annotator', database=db, train_event=te, 
                          annotation_response=annot_resp, socket=socketio)
    monitor = Monitor(name='Monitor', database=db, socket=socketio, 
                      most_important_features=mif, stream=streamer)
    classifier = Classifier(name='Classifier', database=db, model=model_queue,
                            dictionary=d)
    trainer = Trainer(name='Trainer', 
                      clf=SGDClassifier(loss='log', penalty='elasticnet'), 
                      database=db, model=model_queue, train_trigger=te,
                      dictionary=d, most_important_features=mif)

    threads = [streamer, 
               text_processor, 
               monitor,
               classifier,
               trainer
               ]

    for t in threads:
        logging.info(f"Starting {t.name}...")
        t.start()
    
    try:
        socketio.run(app, debug=False, log_output=False)
    except KeyboardInterrupt:
        logging.info("Keyboard Interrupt. Sending stoprequest to all threads")
        annotator.join()
        for t in threads:
            t.join()
        logging.info("Done")
        sys.exit("Main thread stopped by user.")
