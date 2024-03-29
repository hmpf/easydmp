import datetime

from django.utils.timezone import now as utcnow

import factory
import factory.django
from faker import Faker

from easydmp.dmpt.models import BooleanQuestion
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.models import ChoiceQuestion
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import QuestionType
from easydmp.dmpt.models import ReasonQuestion
from easydmp.dmpt.models import ShortFreetextQuestion
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Template


__all__ = [
    'TemplateFactory',
    'SectionFactory',
    'CannedAnswerFactory',
    'QuestionFactory',
    'QuestionTypeFactory',
    'BooleanQuestionFactory',
    'ChoiceQuestionFactory',
    'ReasonQuestionFactory',
    'ShortFreetextQuestionFactory',
    'create_smallest_template',
]


def create_smallest_template(published=None):
    if published is True:
        published = utcnow()
    elif published is not isinstance(published, datetime.datetime):
        published = None
    t = TemplateFactory(published=published)
    s = SectionFactory(template=t)
    qt = QuestionType(id='reason')
    q = QuestionFactory(section=s, input_type=qt)
    return t


class TemplateFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = Template

    title = factory.Faker('sentence', nb_words=6)
    description = factory.Faker('sentence', nb_words=20)
    published = None
    retired = None
    locked = None


class SectionFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = Section

    position = factory.Sequence(lambda n: n)
    template = factory.Iterator(Template.objects.all())
    title = factory.Faker('sentence', nb_words=6)
    introductory_text = factory.Faker('paragraph')


class QuestionTypeFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = QuestionType
        django_get_or_create = ('id',)

    id = factory.Faker('word')


class AbstractQuestionFactory(factory.django.DjangoModelFactory):

    class Meta:
        abstract = True

    question = factory.Faker('sentence', nb_words=10)
    position = factory.Sequence(lambda n: n+1)
    section = factory.Iterator(Section.objects.all())
    on_trunk = True
    help_text = factory.Faker('paragraph')
    input_type = factory.Iterator(QuestionType.objects.all())

    @classmethod
    def _generate(cls, strategy, params):
        obj = super()._generate(strategy, params)
        return obj.get_instance()


class QuestionFactory(AbstractQuestionFactory):

    class Meta:
        model = Question
        django_get_or_create = ('question', 'position')

    input_type = factory.Iterator(QuestionType.objects.all())


class CannedAnswerFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = CannedAnswer

    position = factory.Sequence(lambda n: n)
    question = factory.Iterator(Question.objects.all())
    choice = factory.Faker('word')
    canned_text = factory.Faker('paragraph')


class BooleanQuestionFactory(AbstractQuestionFactory):

    class Meta:
        model = BooleanQuestion
        django_get_or_create = ('question', 'position')

    input_type_id = 'bool'

    @factory.post_generation
    def create_canned_answers(obj, create, extracted):
        # Do not generate ca's
        if extracted is False:
            return
        for choice in ('Yes', 'No'):
            CannedAnswerFactory(question=obj, choice=choice, canned_text=choice)


class ChoiceQuestionFactory(AbstractQuestionFactory):

    class Meta:
        model = ChoiceQuestion
        django_get_or_create = ('question', 'position')

    input_type_id = 'choice'

    @factory.post_generation
    def create_canned_answers(obj, create, extracted, **kwargs):
        count = 3
        if isinstance(extracted, int):
            count = extracted
        # Do not generate ca's
        if not count:
            return
        words = Faker().words(nb=count)
        for word in words:
            CannedAnswerFactory(question=obj, choice=word, **kwargs)


class ReasonQuestionFactory(AbstractQuestionFactory):

    class Meta:
        model = ReasonQuestion
        django_get_or_create = ('question', 'position')

    input_type_id = 'reason'


class ShortFreetextQuestionFactory(AbstractQuestionFactory):

    class Meta:
        model = ShortFreetextQuestion
        django_get_or_create = ('question', 'position')

    input_type_id = 'shortfreetext'
