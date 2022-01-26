from .base import *

STATIC_ROOT = 'staticfiles'
# Changeable settings
EMAIL_HOST = getenv('EMAIL_HOST', None)
assert EMAIL_HOST, 'Env "EMAIL_HOST" not set'
EMAIL_PORT = getenv('EMAIL_PORT', 25)

SECRET_KEY = getenv('SECRET_KEY', None)
assert SECRET_KEY, 'Env "SECRET_KEY" not set'

assert DATABASES.get('default', None), '"DATABASES" must be set'

if not LOGGING_MODULE:
    LOGGING = setup_logging('easydmp.site.logging.DEFAULT')

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

_admins = getenv('ADMINS', '')
if _admins:
    ADMINS = []
    for a in _admins.split(','):
        ADMINS.append(('', a))

INSTALLED_APPS += [
    'social_django',
    'easydmp.theme',
]

AUTHENTICATION_BACKENDS = [
    'dataporten.social.DataportenEmailOAuth2',
    'b2access.B2AccessOAuth2'
] + AUTHENTICATION_BACKENDS

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# Other settings

EASYDMP_SOCIAL_AUTH_LOGIN_MENU = [
    {'slug': 'b2access', 'name': 'B2ACCESS'},
    {'slug': 'dataporten', 'name': 'Dataporten'},
]

SOCIAL_AUTH_DATAPORTEN_EMAIL_KEY = getenv('SOCIAL_AUTH_DATAPORTEN_EMAIL_KEY')
SOCIAL_AUTH_DATAPORTEN_EMAIL_SECRET = getenv('SOCIAL_AUTH_DATAPORTEN_EMAIL_SECRET')
SOCIAL_AUTH_B2ACCESS_KEY = getenv('SOCIAL_AUTH_B2ACCESS_KEY')
SOCIAL_AUTH_B2ACCESS_SECRET = getenv('SOCIAL_AUTH_B2ACCESS_SECRET')
