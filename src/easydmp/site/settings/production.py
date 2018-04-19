import os

import dj_database_url

from .base import *

def getenv(name, default=None):
    value = os.getenv(name, default)
    if isinstance(value, str):
        env = value.strip()
    return value

STATIC_ROOT = 'staticfiles'
# Changeable settings
EMAIL_HOST = getenv('EMAIL_HOST', None)
assert EMAIL_HOST, 'Env "EMAIL_HOST" not set'
EMAIL_PORT = getenv('EMAIL_PORT', 25)

SECRET_KEY = getenv('SECRET_KEY', None)
assert SECRET_KEY, 'Env "SECRET_KEY" not set'

DATABASE_URL = getenv('DMP_DATABASE_URL', None)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL),
    }

try:
    DEBUG
except NameError:
    # Assure that DEBUG is set and safe
    DEBUG = False

try:
    DEBUG = bool(int(getenv('DEBUG', DEBUG)))
except ValueError:
    # Broken env-variable, default to safety
    DEBUG = False

INSTALLED_APPS += [
    'social_django',
    'easydmp.theme',
]

AUTHENTICATION_BACKENDS = [
    'dataporten.social.DataportenEmailOAuth2',
    'b2access.B2AccessOAuth2',
    'django.contrib.auth.backends.RemoteUserBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGGING_CONFIG = None
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'mail_admins'],
            'level': 'DEBUG',
        },
    },
}
import logging.config
logging.config.dictConfig(LOGGING)


SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Other settings

EASYDMP_INVITATION_FROM_ADDRESS = getenv('EASYDMP_INVITATION_FROM_ADDRESS', None)
assert EASYDMP_INVITATION_FROM_ADDRESS, 'Env "EASYDMP_INVITATION_FROM_ADDRESS" not set'

SOCIAL_AUTH_DATAPORTEN_EMAIL_KEY = getenv('SOCIAL_AUTH_DATAPORTEN_EMAIL_KEY')
SOCIAL_AUTH_DATAPORTEN_EMAIL_SECRET = getenv('SOCIAL_AUTH_DATAPORTEN_EMAIL_SECRET')
SOCIAL_AUTH_B2ACCESS_KEY = getenv('SOCIAL_AUTH_B2ACCESS_KEY')
SOCIAL_AUTH_B2ACCESS_SECRET = getenv('SOCIAL_AUTH_B2ACCESS_SECRET')
