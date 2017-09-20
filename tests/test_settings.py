from __future__ import unicode_literals

from django.test.runner import DiscoverRunner

from easydmp.site.settings import base as base_settings

SECRET_KEY = 'fake-key'

INSTALLED_APPS = base_settings.INSTALLED_APPS + [
    'tests',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3',
    }
}
