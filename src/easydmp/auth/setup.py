from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission

from .factories import (
    TemplateDesignerGroupFactory,
    UserFactory,
    SuperuserFactory,
    TemplateDesignerUserFactory,
)


def setup_auth_tables():
    "Fill auth tables with default data"
    # Create "Template Designer" group
    TemplateDesignerGroupFactory()


def setup_dev_users():
    SETUP_PASSWORD = 'niezynarecxaqd'
    superuser = SuperuserFactory(
        username='superuser',
        password=SETUP_PASSWORD
    )
    ordinaryuser = UserFactory(
        username='ordinaryuser',
        password=SETUP_PASSWORD
    )
    template_designer = TemplateDesignerUserFactory(
        username='templatedesigner',
        password=SETUP_PASSWORD
    )
