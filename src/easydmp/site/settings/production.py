import os

import dj_database_url

from .base import *

STATIC_ROOT = 'staticfiles'
# Changeable settings
EMAIL_HOST = os.getenv('EMAIL_HOST', None)
assert EMAIL_HOST, 'Env "EMAIL_HOST" not set'
EMAIL_PORT = os.getenv('EMAIL_PORT', 25)

SECRET_KEY = os.getenv('SECRET_KEY', None)
assert SECRET_KEY, 'Env "SECRET_KEY" not set'

DATABASE_URL = os.getenv('DMP_DATABASE_URL', None)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL),
    }

try:
    DEBUG
except NameError:
    # Assure that DEBUG is set and safe
    DEBUG = False

DEBUG = bool(int(os.getenv('DEBUG', DEBUG)))

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

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Other settings

EASYDMP_INVITATION_FROM_ADDRESS = os.getenv('EASYDMP_INVITATION_FROM_ADDRESS', None)
assert EASYDMP_INVITATION_FROM_ADDRESS, 'Env "EASYDMP_INVITATION_FROM_ADDRESS" not set'

# Remember to add social auth specific settings
