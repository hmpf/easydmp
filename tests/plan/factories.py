import factory

from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan


__all__ = [
    'PlanFactory',
]


class PlanFactory(factory.DjangoModelFactory):

    class Meta:
        model = Plan

    template = factory.Iterator(Template.objects.all())
    title = factory.Faker('sentence', nb_words=6)
