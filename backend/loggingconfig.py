"""
Logging config.
The main goal is to send logs with severity greater or equal ERROR to stderr
and other to stdout.
In order to do that we need filters to separate logs and handlers to
handle each filtered log.

LowerErrorFilter filters log which severity lower than ERROR
UpperErrorFilter filters log which severity greater or equal than ERROR
StdoutStreamHandler sends log to process stdout
StderrStreamHandler sends log to process stderr
"""
import logging
import sys
from collections import defaultdict

import settings


DEBUG = settings.DEVELOPMENT

if DEBUG:
    level = 'DEBUG'
else:
    level = 'INFO'


class StdoutStreamHandler(logging.StreamHandler):
    def __init__(self, stream=sys.__stdout__, *args, **kwargs):
        super().__init__(stream)


class StderrStreamHandler(logging.StreamHandler):
    def __init__(self, stream=sys.__stderr__, *args, **kwargs):
        super().__init__(stream)


class LowerErrorFilter(logging.Filter):
    def filter(self, record): # noqa
        return logging.ERROR < record.levelno


class UpperErrorFilter(logging.Filter):
    def filter(self, record): # noqa
        return logging.ERROR >= record.levelno


def default_logger_factory():
    return {
        'handlers': ['stdout', 'stderr'],
        'level': 'INFO',
        'propagate': True,
    }


DICT_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'class': 'logging.Formatter',
            'format': '%(asctime)s %(name)-15s %(levelname)-8s %(message)s',
        },
        'simple': {
            'class': 'logging.Formatter',
            'format': '%(levelname)s %(message)s',
        },
        'base': {
            'format': (
                '%(asctime)s | '
                '%(levelname)s | '
                '%(name)s - %(module)s | '
                '%(message)s'
            ),
        },

    },
    'filters': {
        'lowererror': {
            'class': 'loggingconfig.LowerErrorFilter',
        },
        'uppererror': {
            'class': 'loggingconfig.UpperErrorFilter',
        },
    },
    'handlers': {
        'stdout': {
            'class': 'loggingconfig.StdoutStreamHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filters': ['lowererror'],
        },
        'stderr': {
            'class': 'loggingconfig.StderrStreamHandler',
            'level': 'ERROR',
            'formatter': 'detailed',
            'filters': ['uppererror'],
        },
        'console': {
            'class': 'logging.StreamHandler',
            'level': level,
            'formatter': 'base',
        },
        'logstash': {
            'class': 'logstash.TCPLogstashHandler',
            'level': 'INFO',
            'host': '10.1.1.229',
            'port': 50000,
            'version': 1,
            'message_type': 'django',
            'fqdn': False,
            'tags': ['django'],
        },
    },
    'loggers': defaultdict(default_logger_factory, {
        'tornado.access': {
            'handlers': ['stdout', 'stderr'],
            'propagate': False,
        },
        'tornado.application': {
            'handlers': ['stdout', 'stderr'],
            'propagate': False,
        },
        'tornado.general': {
            'handlers': ['stdout', 'stderr'],
            'propagate': False,
        },
        'django': {
            'handlers': ['stdout', 'stderr'],
            'propagate': False,
        },
        'django.request': {
            'handlers': ['stdout', 'stderr'],
            'propagate': False,
        },
        'c300': {
            'handlers': ['console'],
            'level': level,
            'propagate': False,
        },
        'c300.telephony': {
            'handlers': ['logstash'],
            'level': 'INFO',
            'propagate': False,
        },
    }),
}

GPRS_DICT_CONFIG = dict(**DICT_CONFIG)
GPRS_DICT_CONFIG['formatters']['detailed']['format'] = (
    '%(asctime)s %(name)-15s :line %(lineno)d: %(levelname)-8s %(message)s'
)
