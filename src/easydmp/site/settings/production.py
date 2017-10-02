from .base import *

INSTALLED_APPS += [
    'social_django',
]

AUTHENTICATION_BACKENDS = [
    'dataporten.social.DataportenFeideOAuth2',
    'django.contrib.auth.backends.RemoteUserBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Remember to add social auth specific settings
