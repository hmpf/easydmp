from __future__ import annotations

import logging.config
import os

from django.utils.module_loading import import_string

from easydmp import __version__ as VERSION

__all__ = [
    'VERSION',
    'updir',
    'pathjoin',
    'getenv',
    'setup_logging',
    'update_loglevels',
]
updir = os.path.dirname
pathjoin = os.path.join


def getenv(name, default=None):
    value = os.getenv(name, default)
    if isinstance(value, str):
        value = value.strip()
    return value


def setup_logging(dotted_path=None):
    '''Use the dictionary on the dotted path to set up logging

    Returns the dictionary on success, otherwise None.
    '''
    if dotted_path:
        try:
            class_or_attr = import_string(dotted_path)
        except AttributeError:
            return
        logging.config.dictConfig(class_or_attr)
        return class_or_attr


def update_loglevels(loglevel: str = 'INFO', loggers=(), handlers=()):
    '''Override specific loglevels in already setup loggers or handlers'''
    loglevel = loglevel.upper()
    for logger in loggers:
        logging.getLogger(logger).setLevel(loglevel)
    if handlers:
        handlerdict = {}
        for handler in handlers:
            handlerdict['handler'] = {'level': loglevel}
        logdict = {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': True,
            'handlers': handlerdict,
        }
        logging.config.dictConfig(logdict)
