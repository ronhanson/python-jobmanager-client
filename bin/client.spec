
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
