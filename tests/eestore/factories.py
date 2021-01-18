import factory

from easydmp.eestore.models import EEStoreType, EEStoreSource


__all__ = [
    'EEStoreTypeFactory',
    'EEStoreSourceFactory',
]


class EEStoreTypeFactory(factory.django.DjangoModelFactory):
    name = factory.Faker('word')

    class Meta:
        model = EEStoreType


class EEStoreSourceFactory(factory.django.DjangoModelFactory):
    eestore_type = factory.SubFactory(EEStoreTypeFactory)
    name = factory.Faker('word')

    class Meta:
        model = EEStoreSource
