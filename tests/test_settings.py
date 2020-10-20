from __future__ import unicode_literals

import os

import dj_database_url

os.environ['EASYDMP_INVITATION_FROM_ADDRESS'] = 'foo@example.com'
from easydmp.site.settings import base as base_settings

MIDDLEWARE = base_settings.MIDDLEWARE

AUTH_USER_MODEL = base_settings.AUTH_USER_MODEL

SECRET_KEY = 'fake-key'

INSTALLED_APPS = base_settings.INSTALLED_APPS + [
    'tests',
]

DATABASE_URL = base_settings.getenv('DMP_DATABASE_URL', 'sqlite://:memory:')
DATABASES = {
    'default': dj_database_url.parse(DATABASE_URL)
}
del DATABASE_URL

TEMPLATES = base_settings.TEMPLATES

LOGIN_URL = base_settings.LOGIN_URL

ROOT_URLCONF = 'easydmp.site.urls'

STATIC_URL = '/static/'

# 3rd party

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend', 'guardian.backends.ObjectPermissionBackend')

EASYDMP_INVITATION_FROM_ADDRESS = getattr(base_settings, 'EASYDMP_INVITATION_FROM_ADDRESS', 'foo@example.com')
