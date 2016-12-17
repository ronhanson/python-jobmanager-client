
[DATABASE]
    HOST = string(default="127.0.0.1")
    PORT = integer(default=27017)
    NAME = string(default="jobmanager")

[CLIENT]
    CLIENT_STATUS_UPDATE_TIMING = integer(default=10)

[JOBS]
    AMOUNT = integer(default=4)
    MODULES = list()

[LOG]
    DEBUG = boolean(default=False)
    LOGGING_FOLDER = string(default='/var/log/<app_name>')
    LOGGING_LEVEL = option("NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", default="INFO")
    LOGGING_METHODS = list(default="SYSLOG")
    LOGGING_SYSLOG_ADDRESS = string(default=None)

    LOGGING_MONGO_HOST = string(default="localhost")
    LOGGING_MONGO_PORT = integer(default=27017)
    LOGGING_MONGO_DATABASE = string(default="jobmanager")
    LOGGING_MONGO_COLLECTION = string(default="jobmanager_logs"
    LOGGING_MONGO_CAPPED = bool(default=True)
    LOGGING_MONGO_CAPPED_MAX = integer(default=1000000)
    LOGGING_MONGO_CAPPED_SIZE = integer(default=50000000)
    LOGGING_MONGO_BUFFER_SIZE = integer(default=50)
    LOGGING_MONGO_BUFFER_FLUSH_LEVEL = integer(default=90)
    LOGGING_MONGO_BUFFER_FLUSH_TIMER = float(default=default=5.0)
