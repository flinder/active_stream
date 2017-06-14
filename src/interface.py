import threading
import logging

from flask import Flask
from flask import render_template
from flask import request


class Interface(threading.Thread):

    def __init__(self, display_queue, annotated_queue, name=None):
        logging.debug('Initializing Interface')
        super(Interface, self).__init__(name=name)
        self.stoprequest = threading.Event()
        self.display_queue = display_queue
        self.annotated_queue = annotated_queue
        logging.debug('Successe')

    def run(self):
        logging.debug('Running')
        app = Flask(__name__, template_folder="../templates")

        @app.route("/", methods=['POST', 'GET'])
        def index():
            if request.method == 'POST':
                logging.debug('Putting status in annotated queue and waiting for new status')
                response = request.form['response']
                logging.debug(f'Got reponse: {response}')


                self.annotated_queue.put(response)
                message = self.display_queue.get()
                return render_template("index.html", tweet_id=message)
            else:
                logging.debug('Waiting for first tweet to display...')
                message = self.display_queue.get()
                return render_template("index.html", tweet_id=message)
               
        app.run(host='0.0.0.0',port=5000,debug=True, use_reloader=False)
