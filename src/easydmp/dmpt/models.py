from django.db import models
from django.utils.encoding import force_text
from django.utils.text import slugify

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
        return self.questions.order_by('position')[0]

    @property
    def last_question(self):
        return self.questions.order_by('-position')[0]

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


class Question(models.Model):
    branching_possible = False

    input_type = models.CharField(
        max_length=max(map(len, INPUT_TYPES)),
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

    def get_class(self):
        return INPUT_TYPE_MAP.get(self.input_type, self.__class__)

    def get_instance(self):
        cls = self.get_class()
        return cls.objects.get(pk=self.pk)

    def _serialize_condition(self, _):
        """
        Convert an answer into a lookup key, if applicable
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

    def map_answers_to_nodes(self, answers):
        "Convert question pks to node pks in the answers, if any"
        data = {}
        for question_pk, answer in answers.items():
            q = Question.objects.get(pk=question_pk)
            if not q.node: continue
            data[str(q.node.pk)] = answer
        return data

    def get_all_next_questions(self):
        return Question.objects.filter(section=self.section, position__gt=self.position)

    def get_next_question(self, answers=None):
        next_questions = self.get_all_next_questions()
        if not next_questions.exists():
            next_section = self.section.get_next_section()
            if next_section:
                return next_section.first_question
            return None

        if not self.node or not self.node.next_nodes.exists():
            return next_questions[0]

        data = self.map_answers_to_nodes(answers)
        next_node = self.node.get_next_node(data)
        if next_node:
            return next_node.payload

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

        if not self.node:
            return list(prev_questions)[-1]

        data = self.map_answers_to_nodes(answers)
        prev_node = self.node.get_prev_node(data)
        if prev_node:
            return prev_node.payload

        return None

class BooleanQuestion(Question):
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'bool'
        super(BooleanQuestion, self).save(*args, **kwargs)

    def _serialize_condition(self, answer):
        """
        answer in (True, False)
        """
        if answer is True:
            return 'Yes'
        if str(answer).lower() in ('true', 'yes', 'on'):
            return 'Yes'
        return 'No'


class ChoiceQuestion(Question):
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'choice'
        super(ChoiceQuestion, self).save(*args, **kwargs)

    def _serialize_condition(self, answer):
        """
        Return answer unchanged
        """
        return answer


class MultipleChoiceOneTextQuestion(Question):

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multichoiceonetext'
        super(MultipleChoiceOneTextQuestion, self).save(*args, **kwargs)

    def get_canned_answer(self, answer, **kwargs):
        """
        answer = ['list', 'of', 'answers']
        """
        if len(answer) == 1:
            return answer[0]

        joined_answer = '{} and {}'.format(', '.join(answer[:-1]), answer[-1])
        if self.framing_text:
            return self.framing_text.format(joined_answer)
        return joined_answer


class DateRangeQuestion(Question):

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'daterange'
        super(DateRangeQuestion, self).save(*args, **kwargs)

    def get_canned_answer(self, daterange, **kwargs):
        """
        daterange = {
            'start': date(),
            'end': date(),
        }
        """
        return self.framing_text.format(**daterange)


class ReasonQuestion(Question):

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'reason'
        super(ReasonQuestion, self).save(*args, **kwargs)

    def get_canned_answer(self, reason, **kwargs):
        """
        reason is a string.
        """
        if self.framing_text:
            return self.framing_text.format(reason)
        return reason


INPUT_TYPE_MAP = {
    'bool': BooleanQuestion,
    'choice': ChoiceQuestion,
    'daterange': DateRangeQuestion,
    'multichoiceonetext': MultipleChoiceOneTextQuestion,
    'reason': ReasonQuestion,
}


class CannedAnswer(models.Model):
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
