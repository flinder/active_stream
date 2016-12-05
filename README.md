# Active learning support for targeted Twitter stream


## About


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
