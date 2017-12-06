from gevent import monkey; monkey.patch_all()
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

# Custom imports
sys.path.append('active_stream/')
from streaming import Streamer, Listener 
from annotation import Annotator
from credentials import credentials
from text_processing import TextProcessor
from monitor import Monitor
from classification import Classifier, Trainer

async_mode = None
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode, logger=False)
thread = None

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html', async_mode=socketio.async_mode)

@socketio.on('connect')
def connected():
    logging.debug('Received connect request')
    emit('log', {'data': 'Connected'})

@socketio.on('tweet_relevant')
def tweet_relevant():
    logging.debug('Received: tweet_relevant')
    emit('log', {'data': 'Connected'})
    annot_resp.put('relevant')

@socketio.on('tweet_irrelevant')
def tweet_irrelevant():
    logging.debug('Received: tweet_irrelevant')
    annot_resp.put('irrelevant')

@socketio.on('refresh')
def tweet_irrelevant():
    logging.debug('Received refresh')
    annot_resp.put('refresh')

@socketio.on('skip')
def tweet_irrelevant():
    logging.debug('Received skip')
    annot_resp.put('skip')

@socketio.on('connect')
def test_connect():
    global annotator
    if annotator.is_alive():
        logging.debug('Annotator already alive. Refreshing')
        emit('keywords', {'keywords': list(streamer.keywords)})
        annotator.first = True
    else:
        logging.info('Starting Annotator.')
        emit('keywords', {'keywords': list(streamer.keywords)})
        annotator.start()

@socketio.on('disconnect_request')
def test_disconnect():
    global annotator
    logging.info('Stopping Annotator.')
    annotator.join()

@socketio.on('add_keyword')
def add_keyword(message):
    logging.debug('Received request to add new keyword. Sending to Streamer.')
    keyword_queue.put({'add': True, 'word': message['data']})

@socketio.on('remove_keyword')
def remove_keyword(message):
    logging.debug('Received request to remove keyword. Sending to Streamer.')
    keyword_queue.put({'add': False, 'word': message['data']})

if __name__ == '__main__':

    # =========================================================================== 
    # Config
    # =========================================================================== 
    no_api = False                # Set to True if no API connection available
                                  # in this case fake 'tweets' are generated
    seed_keywords = []        # Seed keywords
    BUF_SIZE = 1000                # Buffer size of queues
    db = 'active_stream'          # Mongo Database name
    collection = 'dump'           # Mongo db collection name
    filters = {'languages': ['en'], 'locations': []}
    n_before_train = 1
    # =========================================================================== 
    
    # Set up data structures
    text_processor_queue = queue.Queue(BUF_SIZE)
    db = MongoClient()[db][collection]
    model_queue = queue.Queue(1)
    annot_resp = queue.Queue(1)
    te = threading.Event() 
    d = corpora.Dictionary()
    mif = queue.Queue(1)
    keyword_queue = queue.Queue(BUF_SIZE)
    lim_queue = queue.Queue(BUF_SIZE)
    mess_queue = queue.Queue(BUF_SIZE)

    # Clear database
    db.drop()

    # Set up logging
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s (%(threadName)s) %(message)s',
                    #filename='debug.log'
                    ) 


    logging.info('\n'*5)
    logging.info('*'*10 + 'ACTIVE STREAM' + '*'*10)
    logging.info('Starting Application...')

    #for key in logging.Logger.manager.loggerDict:
    #    logging.getLogger(key).setLevel(logging.CRITICAL)

    # Initialize Threads
    streamer = Streamer(name='Streamer', keywords=seed_keywords,
                        credentials=credentials['coll_1'], 
                        tp_queue=text_processor_queue,  
                        filter_params=filters, kw_queue=keyword_queue,
                        limit_queue=lim_queue, message_queue=mess_queue)
    text_processor = TextProcessor(name='Text Processor', database=db,
                                   tp_queue=text_processor_queue, 
                                   dictionary=d)
    annotator = Annotator(name='Annotator', database=db, train_event=te, 
                          annotation_response=annot_resp, socket=socketio,
                          train_threshold=n_before_train,
                          message_queue=mess_queue)
    classifier = Classifier(name='Classifier', database=db, model=model_queue,
                            dictionary=d)
    monitor = Monitor(name='Monitor', database=db, socket=socketio, 
                      most_important_features=mif, stream=streamer,
                      limit_queue=lim_queue, clf=classifier, annot=annotator,
                      message_queue=mess_queue)
    trainer = Trainer(name='Trainer', 
                      clf=SGDClassifier(loss='log', penalty='elasticnet'), 
                      database=db, model=model_queue, train_trigger=te,
                      dictionary=d, most_important_features=mif, 
                      message_queue = mess_queue, stream=streamer)

    threads = [streamer, 
               text_processor, 
               monitor,
               classifier,
               trainer
               ]

    for t in threads:
        logging.info(f'Starting {t.name}...')
        t.start()
    try:
        logging.info('Starting web interface...')
        socketio.run(app, debug=False, log_output=False)
    except KeyboardInterrupt:
        logging.info('Keyboard Interrupt. Sending stoprequest to all threads')
        annotator.join()
        for t in threads:
            logging.debug(f'Sending stoprequest to {t}')
            t.join()
        logging.info('Done')
        sys.exit('Main thread stopped by user.')
