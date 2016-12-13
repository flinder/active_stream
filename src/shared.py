import threading

# Set global variables
ONE_POSITIVE = False
ONE_NEGATIVE = False
RUN_TRAINER = False

database_lock = threading.Condition()

database = []
