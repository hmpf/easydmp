import factory

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from easydmp.auth import factories
from easydmp.auth.models import User


__all__ = [
    'PermissionFactory',
    'UserFactory',
    'SuperuserFactory',
    'TemplateDesignerFactory',
]


class PermissionFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: "Permission %s" % n)
    content_type = factory.Iterator(ContentType.objects.all())
    codename = factory.Sequence(lambda n: "factory_%s" % n)

    class Meta:
        model = Permission

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        for_obj = kwargs.pop('for_model', None)
        permission = super()._create(model_class, *args, **kwargs)
        if not for_obj:
            return super()._create(model_class, *args, **kwargs)
        app, model = for_obj.rsplit('.', 1)
        ct = ContentType.objects.get(app_label=app, model=model)
        permission.content_type = ct
        permission.save()
        return permission


class TestUserFactoryMixin(factory.django.DjangoModelFactory):
    username = factory.Faker('user_name')
    password = 'password'
    email = factory.Faker('email')

    class Meta:
        model = User
        django_get_or_create = ("username",)


class UserFactory(TestUserFactoryMixin, factories.UserFactory):
    pass


class SuperuserFactory(TestUserFactoryMixin, factories.SuperuserFactory):
    pass


class TemplateDesignerFactory(TestUserFactoryMixin, factories.TemplateDesignerUserFactory):
    pass
