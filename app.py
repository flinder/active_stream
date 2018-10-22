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
    data['queues']['annotation_response'].put('relevant')

@socketio.on('tweet_irrelevant')
def tweet_irrelevant():
    logging.debug('Received: tweet_irrelevant')
    data['queues']['annotation_response'].put('irrelevant')

@socketio.on('refresh')
def tweet_irrelevant():
    logging.debug('Received refresh')
    data['queues']['annotation_response'].put('refresh')

@socketio.on('skip')
def tweet_irrelevant():
    logging.debug('Received skip')
    data['queues']['annotation_response'].put('skip')

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
    data['queues']['keywords'].put({'add': True, 'word': message['data']})

@socketio.on('remove_keyword')
def remove_keyword(message):
    logging.debug('Received request to remove keyword. Sending to Streamer.')
    data['queues']['keywords'].put({'add': False, 'word': message['data']})

if __name__ == '__main__':

    # =========================================================================== 
    # Config
    # =========================================================================== 
    BUF_SIZE = 1000                # Maximum size
    db = 'active_stream'          # Mongo Database name
    collection = 'dump'           # Mongo db collection name
    filters = {'languages': ['en'], 'locations': []}
    n_before_train = 10
    # =========================================================================== 
    
    # Set up data structures
    data = {
            'database': MongoClient()[db][collection],
            'queues': {
                'text_processing': queue.Queue(BUF_SIZE),
                'model': queue.Queue(1),
                'annotation_response': queue.Queue(1),
                'most_important_features': queue.Queue(1),
                'keywords': queue.Queue(BUF_SIZE),
                'limit': queue.Queue(BUF_SIZE),
                'messages': queue.Queue(BUF_SIZE)
                },
            'dictionary': corpora.Dictionary(),
            'events': {
                'train_model': threading.Event()
                },
            'filters': filters,
            'socket': socketio,
            }

    # Clear database
    data['database'].drop()

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s (%(threadName)s) %(message)s',
                    filename='debug.log'
                    ) 

    logging.info('\n'*5)
    logging.info('*'*10 + 'ACTIVE STREAM' + '*'*10)
    logging.info('Starting Application...')

    #for key in logging.Logger.manager.loggerDict:
    #    logging.getLogger(key).setLevel(logging.CRITICAL)
    logging.getLogger('socketio').setLevel(logging.ERROR)

    # Initialize Threads
    streamer = Streamer(credentials=credentials['coll_1'], data=data)

    text_processor = TextProcessor(data)
    annotator = Annotator(train_threshold=n_before_train, data=data)
    classifier = Classifier(data)
    monitor = Monitor(streamer=streamer, classifier=classifier, 
                      annotator=annotator, data=data)
    trainer = Trainer(data=data, streamer=streamer,
                      clf=SGDClassifier(loss='log', penalty='elasticnet'))

    threads = [streamer, text_processor, monitor, classifier, trainer]

    for t in threads:
        logging.info(f'Starting {t.name}...')
        t.start()
    
    logging.info('Starting web interface...')
    socketio.run(app, debug=False, log_output=True)
    
    while True:
        try:
            print(streamer.isAlive())
            time.sleep(0.1)
        except KeyboardInterrupt:
            logging.info('Interrupt. Sending stoprequest to all threads')
            annotator.stoprequest.set()
            for t in threads:
                logging.debug(f'Sending stoprequest to {t}')
                t.stoprequest.set()
            logging.info('Done')
            sys.exit('Main thread stopped by user.')
