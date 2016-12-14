# Active learning support for targeted Twitter stream


## About

## Dependencies

* > Python 3.5
* Non-standard Python modules: `tweepy`, `spacy`
* Language data for `spacy` atm english only (`$ python -m spacy.en.download`)
* Mongodb (listening on `localhost:27017` which is default setting when
    installing mongodb)

## Run

Put your twitter credentials in a file named `twitter_credentials.py` of the 
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

Start the application with:
```bash
python active_stream.py
```

Monitor status with:
```bash
tail -f debug.log
```
