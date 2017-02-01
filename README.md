# Active learning support for targeted Twitter stream


## About

The Twitter streaming API allows to track tweets about a specific topic by
tracking user defined keywords. All tweets that contain a keyword can be
accessed (as long as the volume is lower than 1% of total stream). However,
tracking a topic via a keyword has two major disadvantages:

* Keywords allow for crude adjustments of precision / recall tradeoffs. In other
    words in many cases it has poor classification performance
* A researcher / user often does not think of all (or the most useful) keywords
    a priori.

This system is aimed to build a streaming interface that allows the user to
obtain a fine tuned stream that maximizes the number of relevant tweets
from the stream.

The system will consist of four components. Given a few user selected keywords,
an initial stream is produced. The active learning component classifies tweets
as relevant or not and concurrently presents tweets to the user for manual
annotation. Only tweets that the system is most uncertain about are selected for
manual annotation. A second component proposes new keywords based on
co-occurence in the tweet text. The third component is an analytics engine that
provides the user with descriptive information about the relevant tweets that
have been collected so far (not implemented yet). 

## Dependencies

* >= Python 3.5
* Non-standard Python modules: `tweepy`, `spacy`
* Language data for `spacy` atm english only (`$ python -m spacy.en.download`)
* Mongodb (listening on `localhost:27017` which is default setting when
    installing mongodb)

## Run

Put your twitter credentials in a file named `credentials.py` of the 
following format:
```javascript
credentials = {"coll_1": {
        "access_token": "...",
        "access_token_secret": "...",
        "consumer_secret": "...",
        "consumer_key": "...",
    }
}
```

If you don't have twitter credentials or you are offline you can set `no_api = False` in the config
section in `app.py`. The app will then generate artificial tweets that are
sufficient for testing.


Start the application with:
```bash
python app.py
```

Monitor status with:
```bash
tail -f debug.log
```
