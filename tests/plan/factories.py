import factory

from easydmp.plan.models import Plan

from tests.auth.factories import UserFactory
from tests.dmpt.factories import TemplateFactory


__all__ = [
    'PlanFactory',
]


class PlanFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = Plan

    template = factory.SubFactory(TemplateFactory)
    title = factory.Faker('sentence', nb_words=6)
    added_by = factory.SubFactory(UserFactory)
    modified_by = factory.SubFactory(UserFactory)
