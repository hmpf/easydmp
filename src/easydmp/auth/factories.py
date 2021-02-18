import factory

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.models import ContentType

from .models import User

__all__ = [
    'BaseUserFactory',
    'UserFactory',
    'SuperuserFactory',
    'TemplateDesignerUserFactory',
]


class TemplateDesignerGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ('name',)

    name = 'Template Designer'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        group = super()._create(model_class, *args, **kwargs)
        models = ('template', 'section', 'question', 'cannedanswer')
        template_cts = ContentType.objects.filter(app_label='dmpt', model__in=models)
        template_designer_permissions = Permission.objects.filter(
            content_type__in=template_cts).exclude(codename='use_template')
        group.permissions.set(template_designer_permissions)
        return group


class BaseUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)

    is_active = True
    is_staff = False
    is_superuser = False
    password = factory.PostGenerationMethodCall('set_password', 'defaultpassword')


class UserFactory(BaseUserFactory):
    pass


class SuperuserFactory(BaseUserFactory):
    is_staff = True
    is_superuser = True


class TemplateDesignerUserFactory(BaseUserFactory):
    is_staff = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        user = super()._create(model_class, *args, **kwargs)
        group = TemplateDesignerGroupFactory()
        user.groups.add(group)
        return user
