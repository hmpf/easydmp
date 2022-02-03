from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EasyDMPAuthConfig(AppConfig):
    name = 'easydmp.auth'
    verbose_name = _("EasyDMP Authentication and Authorization")
    label = 'easydmp_auth'
