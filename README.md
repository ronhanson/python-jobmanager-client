[![Build Status](https://travis-ci.org/ronhanson/python-jobmanager-client.svg?branch=master)](https://travis-ci.org/ronhanson/python-jobmanager-client)
[![Coverage Status](https://coveralls.io/repos/github/ronhanson/python-jobmanager-client/badge.svg?branch=master)](https://coveralls.io/github/ronhanson/python-jobmanager-client?branch=master)

Job Manager Client
==================

About
-----

This library provides the Job Manager Client package, allowing to run Job/code on a machine or docker container.

Project url : https://github.com/ronhanson/python-jobmanager-client


Usage
-----

Use jobmanager-builder script :

    > bin/jobmanager-client -h

Command lines parameters are as follow :    

    usage: jobmanager-client -s SERVER [-p PORT] [-d DATABASE]
                             [-t JobType [JobType ...]] -i module [module ...]
                             [-l LOG_FILE] [-q]
                             [-v {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                             [-c CONFIG_FILE]
                             [--create-config-file CONFIG_OUTPUT_PATH] [-h]
                             [--version]
    jobmanager-client: error: the following arguments are required: -s/--server, -i/--imports
    (venv) ronand:~/Documents/Sources/code/python-jobmanager-client$ bin/jobmanager-client -h
    usage: jobmanager-client -s SERVER [-p PORT] [-d DATABASE]
                             [-t JobType [JobType ...]] -i module [module ...]
                             [-l LOG_FILE] [-q]
                             [-v {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                             [-c CONFIG_FILE]
                             [--create-config-file CONFIG_OUTPUT_PATH] [-h]
                             [--version]
    
    Job Manager Client Args that start with '--' (eg. -s) can also be set in a
    config file (/etc/jobmanager/client.yaml or ./client.yaml or specified via
    -c). The config file uses YAML syntax and must represent a YAML 'mapping' (for
    details, see http://learn.getgrav.org/advanced/yaml). If an arg is specified
    in more than one place, then commandline values override environment variables
    which override config file values which override defaults.
    
    Job Database:
      -s SERVER, --server SERVER
                            Address of the MongoDB database server containing
                            jobs. [env var: JOBMANAGER_DATABASE_HOST] (default:
                            None)
      -p PORT, --port PORT  Port to connect the MongoDB database. [env var:
                            JOBMANAGER_DATABASE_PORT] (default: 27017)
      -d DATABASE, --database DATABASE
                            Database name containing jobs. [env var:
                            JOBMANAGER_DATABASE_NAME] (default: jobmanager)
    
    Slots & Imports options:
      -t JobType [JobType ...], --slots JobType [JobType ...]
                            Subscribe the current host to one or multiple job
                            type. Use "MyJob==2" to add 2 slots for MyJob type of
                            job. Needs to be written once only. If set to AUTO,
                            each known imported job will have its default amount
                            of slots. [env var: JOBMANAGER_CLIENT_SLOTS] (default:
                            AUTO)
      -i module [module ...], --imports module [module ...]
                            Configure current host to import one or multiple
                            python module at startup. Should not be empty. [env
                            var: JOBMANAGER_CLIENT_IMPORTS] (default: None)
    
    Log output:
      -l LOG_FILE, --log-file LOG_FILE
                            Optionally log to file. [env var:
                            JOBMANAGER_CLIENT_LOG_FILE] (default: None)
      -q, --quiet           Do not output on screen. [env var:
                            JOBMANAGER_CLIENT_QUIET] (default: False)
      -v {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --verbosity {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Log verbosity to screen. [env var:
                            JOBMANAGER_CLIENT_VERBOSITY] (default: INFO)
    
    Config file:
      -c CONFIG_FILE, --config-file CONFIG_FILE
                            config file path (default: None)
      --create-config-file CONFIG_OUTPUT_PATH
                            takes the current command line args and writes them
                            out to a config file at the given path, then exits
                            (default: None)
    
    Miscellaneous commands:
      -h, --help            show this help message and exit.
      --version             show program's version number and exit [env var:
                            JOBMANAGER_CLIENT_VERSION]
    
    "According to this program calculations, there is no such things as too much
    wine."

Example : 

    > bin/jobmanager-builder -s my_mongo_db_server


Compatibility
-------------

This client can be used on Linux, OSX systems, or Windows.

This libraries are compatibles with Python 2.7+ and Python 3.X.

Mainly tested on 2.7, 3.4 and 3.6.


Author & Licence
----------------

Copyright (c) 2007-2018 Ronan Delacroix

This program is released under MIT Licence. Feel free to use it or part of it anywhere you want.
 
