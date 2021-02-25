import factory

from easydmp.auth import factories
from easydmp.auth.models import User


__all__ = [
    'UserFactory',
    'SuperuserFactory',
    'TemplateDesignerFactory',
]


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
