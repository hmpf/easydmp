from .base import *

DEBUG = True
INTERNAL_IPS = ['127.0.0.1']
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG

SECRET_KEY = '=%rr$)2d&hl)#u0kgfgt**%-xmz!#r#1-#px-=nwu)j&2#a-2m'

INSTALLED_APPS += [
    'django_extensions',
    'debug_toolbar',
]

MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
