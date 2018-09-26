"""
WSGI config for easydmp project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/howto/deployment/wsgi/
"""

import sys
import os
from os.path import abspath, dirname

from django.core.wsgi import get_wsgi_application

__root = dirname(dirname(dirname(abspath(__file__))))
sys.path.insert(0, __root)
print('Root of project is at: {}'.format(__root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easydmp.site.settings.dev")
print('Settings used: {}'.format(os.environ.get("DJANGO_SETTINGS_MODULE")))

application = get_wsgi_application()
