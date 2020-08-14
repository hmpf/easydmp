import factory

from easydmp.auth.models import User


__all__ = [
    'UserFactory',
]


class UserFactory(factory.django.DjangoModelFactory):
    usertype = 'default'
    username = factory.Faker('name')
    password = 'password'
    is_active = True
    is_superuser = False
    is_staff = False

    class Meta:
        model = User

    class Params:
        superuser = factory.Trait(
            usertype='superuser',
            is_superuser=True,
            is_staff=True,
        )
        template_designer = factory.Trait(
            usertype='template_designer',
            is_superuser=False,
            is_staff=True,
        )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        manager = cls._get_manager(model_class)
        kwargs.pop('usertype', None)
        username = kwargs.pop('username')
        return manager.create_user(username, **kwargs)
