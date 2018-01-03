from django.db import models
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.html import format_html, escape
from django.utils.text import slugify

from .errors import TemplateDesignError
from easydmp.utils import pprint_list

"""
Question and CannedAnswer have the following API re. Node and Edge:

- They have nullable one to one keys to their respective Nodes and Edges, so
  that they can be designed separately from these and assigned to them later on.
- The Nodes and Edges can reach them through the reverse name "payload"
- They have a property "label" that the Node and Edge can read from
- For easy questions and answers, with no next states, a suitably minimal
  node or edge can be automatically created.
"""

INPUT_TYPES = (
    'bool',
    'choice',
    'daterange',
    'multichoiceonetext',
    'reason',
    'positiveinteger',
    'externalchoice',
    'externalmultichoiceonetext',
    'namedurl',
    'multinamedurlonetext',
)


def _force_items_to_str(dict_):
    return {force_text(k): force_text(v) for k, v in dict_.items()}


class Template(models.Model):
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=8, blank=True)
    version = models.PositiveIntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)
    published = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('version', 'title')

    def __str__(self):
        if self.abbreviation:
            return self.abbreviation
        return self.title

    @property
    def questions(self):
        return Question.objects.filter(section__template=self)

    @property
    def first_section(self):
        return Section.objects.filter(template=self).order_by('position')[0]

    @property
    def last_section(self):
        return Section.objects.filter(template=self).order_by('-position')[0]

    @property
    def first_question(self):
        section = self.first_section
        return section.first_question

    @property
    def last_question(self):
        section = self.last_section
        return section.last_question

    def generate_canned_text(self, data):
        texts = []
        for section in self.sections.order_by('position'):
            texts.append({
                'section': section,
                'text': section.generate_canned_text(data),
            })
        return texts


class Section(models.Model):
    """A section of a :model:`dmpt.Template`.

    **Attributes**

    template: The template this section is part of
    title: Name of section. Can be empty if a template only has one section
    position: Position when there is more than one section. 1 otherwise.
    introductory_text: Canned text printed before the canned texcts of the sections' questions.

    A template has at least one section, which is why the title is optional and
    the default position is 1. A specific title and a specific position can
    only be used once per template, this is checked when attempting to save.
    """
    template = models.ForeignKey(Template, related_name='sections')
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text='May be empty for **one** section per template',
    )
    position = models.PositiveIntegerField(
        default=1,
        help_text='A specific position may only occur once per template',
    )
    introductory_text = models.TextField(blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = (
            ('template', 'title'),
            ('template', 'position'),
        )

    def __str__(self):
        return '{}: {}'.format(self.template, self.title)

    @property
    def first_question(self):
        if self.questions.exists():
            return self.questions.order_by('position')[0]
        # See if there is a next section in case this one has no questions
        next_section = self.get_next_section()
        if next_section:
            return next_section.first_question
        return None

    @property
    def last_question(self):
        if self.questions.exists():
            return self.questions.order_by('-position')[0]
        # See if there is a prev section in case this one has no questions
        prev_section = self.get_prev_section()
        if prev_section:
            return prev_section.last_question
        return None

    def generate_canned_text(self, data):
        texts = []
        for question in self.questions.order_by('position'):
            texts.append(question.get_instance().generate_canned_text(data))
        return texts

    def get_all_next_sections(self):
        return Section.objects.filter(template=self.template, position__gt=self.position)

    def get_next_section(self):
        next_sections = self.get_all_next_sections().order_by('position')
        if next_sections.exists():
            return next_sections[0]
        return None

    def get_all_prev_sections(self):
        return Section.objects.filter(template=self.template, position__lt=self.position)

    def get_prev_section(self):
        prev_sections = self.get_all_prev_sections().order_by('-position')
        if prev_sections.exists():
            return prev_sections[0]
        return None


class SimpleFramingTextMixin:
    """Generate a canned answer for a non-branching, atomic type

    This includes strings, but excludes any other iterables.
    """
    def get_canned_answer(self, choice, **kwargs):
        choice = str(choice)
        return self.frame_canned_answer(choice)


class Question(models.Model):
    """The database representation of a question

    Questions come in many subtypes, stored in `input_type`.

    To convert a question to its subtype, run `get_class()` for the class of an
    instance and `get_instance()` for the instance itself.

    If branching_possible is True:

    * The question *must* have at least one `CannedAnswer`
    * If branching, the `CannedAnswer.choice` must reflect a
      `flow.Edge.condition`. This is set by `map_choice_to_condition()`

    If branching_possible is False:

    * The question need not have a `CannedAnswer`.
    * The `choice` is converted to an empty string.
    """
    branching_possible = False

    input_type = models.CharField(
        max_length=32,
        choices=zip(INPUT_TYPES, INPUT_TYPES),
    )
    section = models.ForeignKey(Section, related_name='questions')
    position = models.PositiveIntegerField(
        default=1,
        help_text='Position in section. Must be unique.',
    )
    label = models.CharField(max_length=16, blank=True)
    question = models.CharField(max_length=255)
    help_text = models.TextField(blank=True)
    framing_text = models.TextField(blank=True)
    comment = models.TextField(blank=True, null=True)
    node = models.OneToOneField('flow.Node', related_name='payload',
                                blank=True, null=True)

    class Meta:
        unique_together = ('section', 'position')
        ordering = ('section', 'position')

    def __str__(self):
        if self.label:
            return '{} {}'.format(self.label, self.question)
        return self.question

    def legend(self):
        qstring = str(self)
        return '{}({}): {}'.format(self.section.template, self.section.position, qstring)

    def get_class(self):
        """Get the correct class of a raw Question-instance

        The subtype is stored in the attribute `input_type`
        """
        return INPUT_TYPE_MAP.get(self.input_type, self.__class__)

    def get_instance(self):
        """Convert a raw Question-instance to its subtype

        The subtype is stored in the attribute `input_type`i
        """
        cls = self.get_class()
        return cls.objects.get(pk=self.pk)

    def _serialize_condition(self, _):
        """Convert an answer into a lookup key, if applicable

        This is only applicable if `branching_possible` is True.
        """
        return NotImplemented

    def generate_canned_text(self, data):
        answer = data.get(str(self.pk), {})
        choice = answer.get('choice', None)
        canned = ''
        if choice:
            canned = self.get_canned_answer(choice)
        answer['text'] = canned
        return answer

    def get_canned_answer(self, answer, **kwargs):
        if not self.canned_answers.exists():
            return ''

        if self.canned_answers.count() == 1:
            return self.canned_answers.get().canned_text

        choice = self._serialize_condition(answer)
        canned = self.canned_answers.get(choice=choice).canned_text
        if not canned:
            canned = answer
        return canned

    def pprint(self, value):
        "Return a plaintext representation of the `choice`"
        return value['choice']

    def pprint_html(self, value):
        "Return an HTML representation of the `choice`"
        return self.pprint(value)

    def create_node(self, fsa=None):
        from flow.models import Node, FSA
        label = self.label if self.label else self.id
        if not fsa:
            fsa = FSA.objects.create(slug='fsa-{}'.format(label))
        self.node = Node.objects.create(
            slug=slugify(label),
            fsa=fsa,
        )
        self.save()

    def map_choice_to_condition(self, answer):
        """Convert the `choice` in an answer to an Edge.condition

        The choice is unwrapped from its structure, and set to empty if the
        question type cannot branch.
        """
        condition = ''
        if self.branching_possible:
            # The choice is used to look up an Edge.condition
            condition = str(answer.get('choice', ''))
        return condition

    @classmethod
    def map_answers_to_nodes(self, answers):
        "Convert question pks to node pks, and choices to conditions"
        data = {}
        for question_pk, answer in answers.items():
            q = Question.objects.get(pk=question_pk)
            if not q.node: continue
            q = q.get_instance()
            condition = q.map_choice_to_condition(answer)
            data[str(q.node.slug)] = condition
        return data

    def get_first_question_in_next_section(self):
        next_section = self.section.get_next_section()
        if next_section:
            return next_section.first_question
        return None

    def get_all_next_questions(self):
        return Question.objects.filter(section=self.section, position__gt=self.position)

    def get_next_question(self, answers=None):
        next_questions = self.get_all_next_questions()
        if not next_questions.exists():
            return self.get_first_question_in_next_section()

        if not self.node:
            return next_questions[0]

        if self.node.end:
            # Break out of section because fsa.end == True
            return self.get_first_question_in_next_section()

        if not self.node.next_nodes.exists():
            return next_questions[0]

        data = self.map_answers_to_nodes(answers)
        next_node = self.node.get_next_node(data)
        if next_node:
            # Break out of section because fsa.end == True
            if next_node.end:
                return self.get_first_question_in_next_section()
            # Not at the end, get payload
            try:
                return next_node.payload
            except Question.DoesNotExist:
                raise TemplateDesignError('Error in template design: next node ({}) is not hooked up to a question'.format(next_node))

        return None

    def get_all_prev_questions(self):
        return Question.objects.filter(section=self.section, position__lt=self.position)

    def get_prev_question(self, answers=None):
        prev_questions = self.get_all_prev_questions()
        if not prev_questions.exists():
            prev_section = self.section.get_prev_section()
            if prev_section:
                return prev_section.last_question
            return None

        if not self.node or self.node.start:
            return list(prev_questions)[-1]

        data = self.map_answers_to_nodes(answers)
        prev_node = self.node.get_prev_node(data)
        if prev_node:
            try:
                return prev_node.payload
            except Question.DoesNotExist:
                raise TemplateDesignError('Error in template design: prev node ({}) is not hooked up to a question'.format(prev_node))

        return None

    def frame_canned_answer(self, answer):
        if self.framing_text:
            return self.framing_text.format(answer)
        return answer


class BooleanQuestion(Question):
    """A branch-capable question answerable with "Yes" or "No"

    The choice is converted to True or False.
    """
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'bool'
        super().save(*args, **kwargs)

    def _serialize_condition(self, answer):
        """
        answer in (True, False)
        """
        if answer is True:
            return 'Yes'
        if str(answer).lower() in ('true', 'yes', 'on'):
            return 'Yes'
        return 'No'

    def pprint(self, value):
        return 'Yes' if value['choice'] else 'No'


class ChoiceQuestion(Question):
    "A branch-capable question answerable with one of a small set of choices"
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'choice'
        super().save(*args, **kwargs)

    def _serialize_condition(self, answer):
        """
        Return answer unchanged
        """
        return answer


class MultipleChoiceOneTextQuestion(Question):
    "A non-branch-capable question answerable with one or more of a small set of choices"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multichoiceonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, answer, **kwargs):
        """
        answer = ['list', 'of', 'answers']
        """

        if not answer:
            return ''

        if len(answer) == 1:
            return self.frame_canned_answer(answer[0])

        joined_answer = '{} and {}'.format(', '.join(answer[:-1]), answer[-1])
        return self.frame_canned_answer(joined_answer)

    def pprint(self, value):
        return pprint_list(value['choice'])


class DateRangeQuestion(Question):
    "A non-branch-capable question answerable with a daterange"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'daterange'
        super().save(*args, **kwargs)

    def get_canned_answer(self, daterange, **kwargs):
        """
        daterange = {
            'start': date(),
            'end': date(),
        }
        """
        framing_text = self.framing_text
        if not framing_text:
            framing_text = 'From {start} to {end}'
        return framing_text.format(**daterange)

    def pprint(self, value):
        return self.framing_text.format(**value['choice'])


class ReasonQuestion(SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with plaintext"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'reason'
        super().save(*args, **kwargs)


class PositiveIntegerQuestion(SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with a positive integer"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'positiveinteger'
        super().save(*args, **kwargs)


class ExternalChoiceQuestion(Question):
    """A non-branch-capable question answerable with a single choice

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStorePluginMount`. This is used when there are
    too many for a drop down/radio field list.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'externalchoice'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        answers = self.eestore.get_cached_entries()
        try:
            answer = answers.get(eestore_pid=choice)
        except answers.model.DoesNotExist:
            # Prevent 500 if the EE cache is empty
            return ''
        return self.frame_canned_answer(answer.name)

    def pprint(self, value):
        return value['text']


class ExternalMultipleChoiceOneTextQuestion(Question):
    """A non-branch-capable question answerable with multiple choices

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStorePluginMount`. This is used when there are
    too many for a standard multiselect.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'externalmultichoiceonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        """
        choice = ['list', 'of', 'answers']
        """
        answers = self.eestore.get_cached_entries()
        answer = tuple(answers.filter(eestore_pid__in=choice).values_list('name', flat=True))

        if not answer: # Prevent 500 if the EE cache is empty
            return ''

        if len(answer) == 1:
            canned_answer = answer[0]
        else:
            canned_answer = '{} and {}'.format(', '.join(answer[:-1]), answer[-1])
        return self.frame_canned_answer(canned_answer)

    def pprint(self, value):
        return value['text']


class NamedURLQuestion(Question):
    """A non-branch-capable question answerable with an url

    A name/title/description for the url is optional.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'namedurl'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        if not choice.get('name', None):
            answer = choice['url']
        else:
            answer = '{url} "{name}"'.format(**choice)
        return self.frame_canned_answer(answer)

    def pprint(self, value):
        url = value['choice']['url']
        name = value['choice'].get('name', None)
        if name:
            return '{url} ({name})'.format(url=url, name=name)
        return url

    def pprint_html(self, value):
        url = value['choice']['url']
        name = value['choice'].get('name', url)
        return format_html('<a href="{}">{}</a>', url, name)


class MultiNamedURLOneTextQuestion(Question):
    """A non-branch-capable question answerable with several urls

    A name/title/description per url is optional.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multinamedurlonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        urlpairs = []
        for pair in choice:
            if not pair.get('name', None):
                urlpairs.append(pair['url'])
            else:
                urlpairs.append('{url} "{name}"'.format(**pair))

        if len(urlpairs) == 1:
            if self.framing_text:
                return self.framing_text.format(urlpairs[0])
            return urlpairs[0]

        joined_pairs = '{} and {}'.format(', '.join(urlpairs[:-1]), urlpairs[-1])
        return self.frame_canned_answer(joined_pairs)

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        urlpairs = []
        for choice in choices:
            url = choice['url']
            name = choice.get('name', '') or url
            urlpairs.append('<a href="{}">{}</a>'.format(url, escape(name)))

        if len(urlpairs) == 1:
            return mark_safe(urlpairs[0])

        joined_pairs = '{} and {}'.format(', '.join(urlpairs[:-1]), urlpairs[-1])
        if self.framing_text:
            return mark_safe(self.framing_text.format(joined_pairs))
        return mark_safe(joined_pairs)


INPUT_TYPE_MAP = {
    'bool': BooleanQuestion,
    'choice': ChoiceQuestion,
    'daterange': DateRangeQuestion,
    'multichoiceonetext': MultipleChoiceOneTextQuestion,
    'reason': ReasonQuestion,
    'positiveinteger': PositiveIntegerQuestion,
    'externalchoice': ExternalChoiceQuestion,
    'externalmultichoiceonetext': ExternalMultipleChoiceOneTextQuestion,
    'namedurl': NamedURLQuestion,
    'multinamedurlonetext': MultiNamedURLOneTextQuestion,
}


class CannedAnswer(models.Model):
    "Defines the possible answers for a branch-capable question"
    question = models.ForeignKey(Question, related_name='canned_answers')
    choice = models.CharField(max_length=255,
                              help_text='Human friendly view of condition')
    canned_text = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    edge = models.OneToOneField('flow.Edge', related_name='payload', blank=True,
                           null=True)

    @property
    def label(self):
        return self.choice

    def __str__(self):
        return '{}: "{}" {}'.format(self.question.question, self.choice, self.canned_text)

    def convert_choice_to_condition(self):
        if self.question.input_type == 'bool':
            condition = 'False'
            if self.choice.lower() in ('yes', 'true', 'on', 'ok', 't'):
                condition = 'True'
        else:
            condition = slugify(self.label)[:16]
        return condition

    def create_edge(self):
        from flow.models import Edge
        if not self.question.node:
            self.question.create_node()
        condition = self.convert_choice_to_condition()
        self.edge = Edge.objects.create(
            condition=condition,
            prev_node=self.question.node,
            next_node=None
        )
        self.save()

    def update_edge(self):
        condition = self.convert_choice_to_condition()
        self.edge.condition = condition
        self.edge.save()
