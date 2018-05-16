from collections import OrderedDict
from copy import deepcopy
from functools import lru_cache
from textwrap import fill
from uuid import uuid4
import logging

LOG = logging.getLogger(__name__)

import graphviz as gv

from django.apps import apps
from django.contrib.admin.utils import NestedObjects
from django.db import models
from django.db import router
from django.db import transaction
from django.db.models import Q
from django.forms import model_to_dict
from django.template import engines, Context
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.html import format_html, escape
from django.utils.text import slugify

from flow.graphviz import _prep_dotsource, view_dotsource, render_dotsource_to_file

from .errors import TemplateDesignError
from .utils import *
from easydmp.eestore.models import EEStoreCache
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
    'extchoicenotlisted',
    'externalmultichoiceonetext',
    'extmultichoicenotlistedonetext',
    'namedurl',
    'multinamedurlonetext',
    'multidmptypedreasononetext',
)


def dfs_paths(graph, start):
    """Find all paths in  DAG graph, return a generator of lists

    Input: adjacency list in a dict:

    {
        node1: set([node1, node2, node3]),
        node2: set([node2, node3]),
        node3: set(),
    }
    """
    stack = [(start, [start])]
    visited = set()
    while stack:
        # loop detection
        if start in visited:
            error = 'Graph is not a DAG, there\'s a loop for node "{}"'
            raise TypeError(error.format(start))
        (vertex, path) = stack.pop()
        if not graph.get(vertex, None):
            yield path
        for next in graph[vertex] - set(path):
            if not next:
                yield path + [next]
            else:
                stack.append((next, path + [next]))


class Template(DeletionMixin, RenumberMixin, models.Model):
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

    def collect(self, using='default', **kwargs):
        collector = super().collect(using=using, **kwargs)
        if self.questions.exists():
            Edge = apps.get_model('flow', 'Edge')
            nodes = [q.node for q in self.questions.all() if q.node]
            fsas = set(n.fsa for n in nodes)
            collector.collect(tuple(fsas))
            edges = set()
            for n in nodes:
                edges.update(set(n.next_nodes.all() | n.prev_nodes.all()))
            collector.collect(tuple(edges))
        return collector

    @transaction.atomic
    def clone(self, title=None):
        """Clone the template and save it as <title>

        If <title> is not given, add a random uuid to the existing ``title``.
        The version is reset to 1 and the new template is hidden from view by
        ``published`` not being set.

        Also recursively clones all sections, questions, canned answers,
        EEStore mounts, FSAs, nodes and edges."""
        if not title:
            title = '{} ({})'.format(self.title, uuid4())
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'title',
                                                 'version', 'published'])
        new = self.__class__.objects.create(title=title, version=1, **self_dict)
        # clone sections, which clones questions, canned answers, fsas and eestore mounts
        section_mapping = {}
        for section in self.sections.all():
            new_section = section.clone(new)
            section_mapping[section] = new_section
        for old_section, new_section in section_mapping.items():
            if old_section.super_section:
                new_section.super_section = section_mapping[old_section.super_section]
                new_section.save()
        return new

    def renumber_positions(self):
        """Renumber section positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        sections = self.sections.order_by('position')
        self._renumber_positions(sections)

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
            canned_text = section.generate_canned_text(data)
            section_dict = model_to_dict(section, exclude=('_state', '_template_cache'))
            section_dict['introductory_text'] = mark_safe(section_dict['introductory_text'])
            texts.append({
                'section': section_dict,
                'text': canned_text,
            })
        return texts

    def get_summary(self, data):
        summary = OrderedDict()
        data = deepcopy(data)  # 1/2 Make absolutely sure we're working on a copy
        for section in self.sections.order_by('position'):
            section_summary = OrderedDict()
            for question in section.find_minimal_path(data):
                value = {}
                question = question.get_instance()
                answer = data.get(str(question.pk), None)
                if not answer or answer.get('choice', None) is None:
                    value['answer'] = None
                else:
                    value['answer'] = question.pprint_html(answer)
                # 2/2 Otherwise this might edit the actual plan data in memory!
                # Mutable types strike back..
                value['question'] = question
                section_summary[question.pk] = value
            summary[section.full_title()] = {
                'data': section_summary,
                'section': {
                    'depth': section.section_depth,
                    'label': section.label,
                    'title': section.title,
                    'section': section,
                    'full_title': section.full_title(),
                    'pk': section.pk,
                    'first_question': section.get_first_question(),
                    'introductory_text': mark_safe(section.introductory_text),
                    'comment': mark_safe(section.comment),
                }
            }
        return summary

    def list_unknown_questions(self, plan):
        "List out all question pks of a plan that are unknown in the template"
        assert self == plan.template, "Mrong template for plan"
        question_pks = self.questions.values_list('pk', flat=True)
        data_pks = set(int(k) for k in plan.data)
        return data_pks.difference(question_pks)

    def validate_plan(self, plan, recalculate=True):
        wrong_pks = [str(pk) for pk in self.list_unknown_questions(plan)]
        if wrong_pks:
            error = 'The plan {} contains nonsense data: template has no questions for: {}'
            planstr = '{} ({}), template {} ({})'.format(plan, plan.pk, self, self.pk)
            LOG.error(error.format(planstr, ' '.join(wrong_pks)))
            return False
        if not plan.data:
            error = 'The plan {} ({}) has no data: invalid'
            LOG.error(error.format(plan, plan.pk))
            return False
        if recalculate:
            for section in self.sections.all():
                valids, invalids = section.find_validity_of_questions(plan.data)
                section.set_validity_of_questions(plan, valids, invalids)
            valids, invalids = self.find_validity_of_sections(plan.data)
            self.set_validity_of_sections(plan, valids, invalids)
        if plan.section_validity.filter(valid=True).count() == plan.template.sections.count():
            return True
        return False

    def find_validity_of_sections(self, data):
        valid_sections = []
        invalid_sections = []
        for section in self.sections.all():
            if section.validate_data(data):
                valid_sections.append(section)
            else:
                invalid_sections.append(section)
        return (valid_sections, invalid_sections)

    def set_validity_of_sections(self, plan, valids, invalids):
        plan.set_sections_as_valid(*valids)
        plan.set_sections_as_invalid(*invalids)

    def validate_data(self, data):
        if not data:
            return False
        _, invalid_sections = self.find_validity_of_sections(data)
        return False if invalid_sections else True


class Section(DeletionMixin, RenumberMixin, models.Model):
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
    GRAPHVIZ_TMPDIR = '/tmp/dmpt/'
    template = models.ForeignKey(Template, related_name='sections')
    label = models.CharField(max_length=16, blank=True)
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
    super_section = models.ForeignKey('self', null=True, blank=True, related_name='subsections')
    section_depth = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = (
            ('template', 'title'),
            ('template', 'position'),
        )

    @lru_cache(None)
    def __str__(self):
        return '{}: {}'.format(self.template, self.full_title())

    def full_title(self):
        if self.label:
            return '{} {}'.format(self.label, self.title)
        return self.title

    @transaction.atomic
    def clone(self, template):
        """Make a complete copy of the section and put it in <template>

        Copies questions, canned answers, EEStore mounts, FSAs, nodes and edges.
        """
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'template', 'super_section'])
        new = self.__class__.objects.create(template=template, **self_dict)
        question_mapping = {}
        for question in self.questions.all():
            question_mapping[question] = question.clone(new)
        self.clone_fsas(question_mapping, new)
        return new

    @transaction.atomic
    def clone_fsas(self, question_mapping, section):
        """Clone FSAs, which also clones nodes and edges

        Hook up nodes and edges of the FSAs to questions and canned answers."""
        node_questions = self.questions.prefetch_related('canned_answers').filter(node__isnull=False)
        fsas = [q.node.fsa for q in node_questions.distinct()]
        fsa_mapping = {}
        # clone fsa
        for fsa in fsas:
            title = 's{}-{}'.format(section.pk, fsa.slug)
            fsa_mapping[fsa] = fsa.clone(title)
        # hook up new questions to new fsa nodes
        Edge = apps.get_model('flow', 'Edge')
        edge_qs = Edge.objects.select_related('prev_node')
        for question in node_questions:
            node = question.node
            new_fsa = fsa_mapping[node.fsa]
            new_node = new_fsa.nodes.get(slug=node.slug)
            new_question = question_mapping[question]
            new_question.node = new_node
            new_question.save()
            # hook up new canned answers to new fsa edges
            old_edges = edge_qs.filter(prev_node=question.node)
            new_edges = edge_qs.filter(prev_node=new_question.node)
            edge_mapping = {edge: new_edges.get(condition=edge.condition) for edge in old_edges}
            for ca in question.canned_answers.filter(edge__isnull=False):
                new_ca = new_question.canned_answers.get(choice=ca.choice)
                new_ca.edge = edge_mapping[ca.edge]
                new_ca.save()

    def collect(self, using='default', **kwargs):
        collector = super().collect(using=using, **kwargs)
        if self.questions.exists():
            Edge = apps.get_model('flow', 'Edge')
            nodes = [q.node for q in self.questions.all() if q.node]
            fsas = set(n.fsa for n in nodes)
            collector.collect(tuple(fsas))
            edges = set()
            for n in nodes:
                edges.update(set(n.next_nodes.all() | n.prev_nodes.all()))
            collector.collect(tuple(edges))
        return collector

    def renumber_positions(self):
        """Renumber question positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        questions = self.questions.order_by('position')
        self._renumber_positions(questions)

    def get_first_question(self):
        if self.questions.exists():
            return self.questions.order_by('position')[0]
        return None

    @property
    def first_question(self):
        first_question = self.get_first_question()
        if first_question:
            return first_question
        # See if there is a next section in case this one has no questions
        next_section = self.get_next_section()
        if next_section:
            return next_section.first_question
        return None

    def get_last_question(self, in_section=False):
        if self.questions.exists():
            return self.questions.order_by('-position')[0]
        return None

    @property
    def last_question(self):
        last_question = self.get_last_question()
        if last_question:
            return last_question
        # See if there is a prev section in case this one has no questions
        prev_section = self.get_prev_section()
        if prev_section:
            return prev_section.last_question
        return None

    def generate_canned_text(self, data):
        texts = []
        for question in self.questions.order_by('position'):
            answer = question.get_instance().generate_canned_text(data)
            if not isinstance(answer.get('text', ''), bool):
                texts.append(answer)
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

    def get_topmost_section(self):
        obj = self
        while obj.super_section is not None:
            obj = obj.super_section
        return obj

    def find_validity_of_questions(self, data):
        assert data, 'No data, cannot validate'
        questions = self.questions.all()
        valids = []
        invalids = []
        for question in questions:
            question = question.get_instance()
            try:
                valid = question.validate_data(data)
            except AttributeError:
                valid = False
            if valid:
                valids.append(question)
            else:
                invalids.append(question)
        return (valids, invalids)

    def set_validity_of_questions(self, plan, valids, invalids):
        plan.set_questions_as_valid(*valids)
        plan.set_questions_as_invalid(*invalids)

    def validate_data(self, data):
        if not data:
            return False
        if not self.questions.exists():
            return True
        valids, invalids = self.find_validity_of_questions(data)
        if not invalids:
            return True
        valid_pks = set(q.pk for q in valids)
        for path in self.find_all_paths():
            if valid_pks == set(path):
                return True
        return False

    def find_minimal_path(self, data=None):
        minimal_qs = self.questions.filter(obligatory=True).order_by('position')
        if not data:
            return list(minimal_qs)
        answered_pks = [int(pk) for pk in data.keys()]
        answered_qs = self.questions.filter(pk__in=answered_pks)
        qs = minimal_qs | answered_qs
        return list(qs.distinct().order_by('position'))

    def find_all_paths(self):
        qs = self.questions.all()
        adjacent = {}
        for q in qs:
            adjacent[q.pk] = set(i.pk if i else None for i in q.get_potential_next_questions())
        paths = []
        for path in dfs_paths(adjacent, self.first_question.pk):
            if not path[-1]:
                path = path[:-1]
            paths.append(path)
        return paths

    # graphing code
    def find_path(self, data):
        if not data:
            return []
        if not self.questions.exists():
            # No path in this section
            return []
        all_in_section = set(self.questions.all())
        path = []
        next = self.first_question
        while next and all_in_section:
            path.append(next)
            all_in_section.discard(next)
            if next.is_last_in_section():
                break
            try:
                next = next.get_next_question(data, in_section=True)
            except TemplateDesignError:
                # section end, probably
                break
            except KeyError:
                # template likely has changed
                break
        return path

    @staticmethod
    def generate_forwards_path(path):
        """Turn [1, 2, 3] into {1: 2, 2: 3, 3: None}"""
        forwards_path = {}
        if path:
            for i, pk in enumerate(path[:-1]):
                forwards_path[pk] = path[i+1]
            forwards_path[path[-1]] = None
        return forwards_path

    @staticmethod
    def generate_backwards_path(path):
        """Turn [1, 2, 3] into {1: None, 2: 1, 3: 2}"""
        path = reversed(path)
        return self.generate_forwards_path(path)

    def generate_dotsource(self):
        global gv
        dot = gv.Digraph()

        s_kwargs = {'shape': 'doublecircle'}
        s_start_id = 's-{}-start'.format(self.pk)
        dot.node(s_start_id, label='Start', **s_kwargs)
        s_end_id = 's-{}-end'.format(self.pk)
        dot.node(s_end_id, label='End', **s_kwargs)
        for question in self.questions.order_by('position'):
            q_kwargs = {}
            q_kwargs['label'] = fill(str(question), 20)
            q_id = 'q{}'.format(question.pk)
            if question.pk == self.get_first_question().pk:
                dot.edge(s_start_id, q_id, **s_kwargs)
            dot.node(q_id, **q_kwargs)
            next_questions = question.get_potential_next_questions_with_edge()
            if next_questions:
                for choice, next_question in next_questions:
                    if next_question:
                        nq_id = 'q{}'.format(next_question.pk)
                    else:
                        nq_id = s_end_id
                    e_kwargs = {'label': fill(choice, 15)}
                    dot.edge(q_id, nq_id, **e_kwargs)
            else:
                dot.edge(q_id, s_end_id)
        return dot.source

    def view_dotsource(self, format, dotsource=None):  # pragma: no cover
        if not dotsource:
            dotsource = self.generate_dotsource()
        view_dotsource(format, dotsource, self.GRAPHVIZ_TMPDIR)

    def render_dotsource_to_file(self, format, filename, directory='', dotsource=None):
        _prep_dotsource(self.GRAPHVIZ_TMPDIR)
        if not dotsource:
            dotsource = self.generate_dotsource()
        return render_dotsource_to_file(format, filename, dotsource, self.GRAPHVIZ_TMPDIR, directory)


class NoCheckMixin:

    def is_valid(self):
        return True


class SimpleFramingTextMixin:
    """Generate a canned answer for a non-branching, atomic type

    This includes strings, but excludes any other iterables.
    """
    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return ''

        choice = str(choice)
        return self.frame_canned_answer(choice, frame)

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if choice:
            return True
        return False


class Question(DeletionMixin, RenumberMixin, models.Model):
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
    has_notes = True

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
    obligatory = models.NullBooleanField(blank=True, null=True)
    node = models.OneToOneField('flow.Node', related_name='payload',
                                blank=True, null=True,
                                on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('section', 'position')
        ordering = ('section', 'position')
        indexes = [
            models.Index(fields=['input_type', 'id']),
            models.Index(fields=['section', 'position']),
        ]

    @lru_cache(None)
    def __str__(self):
        if self.label:
            return '{} {}'.format(self.label, self.question)
        return self.question

    def collect(self, using='default', **kwargs):
        collector = super().collect(using=using, **kwargs)
        if self.node:
            edges = set(self.node.next_nodes.all() | self.node.prev_nodes.all())
            collector.collect(tuple(edges))
            collector.collect([self.node])
        return collector

    @transaction.atomic
    def clone(self, section):
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'section', 'node'])
        new = self.__class__.objects.create(section=section, **self_dict)
        for ca in self.canned_answers.all():
            ca.clone(new)
        if getattr(self, 'eestore', None):
            self.eestore.clone(new)
        return new

    def renumber_positions(self):
        """Renumber canned answer positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        cas = self.canned_answers.order_by('position')
        if cas.count() > 1:
            self._renumber_positions(cas)

    def is_valid(self):
        raise NotImplementedError

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

        The subtype is stored in the attribute `input_type`
        """
        cls = self.get_class()
        self.__class__ = cls
        return self

    def get_choices(self):
        raise NotImplementedError

    def get_choices_keys(self):
        choices = self.get_choices()
        return [item[0] for item in choices]

    def validate_data(self, data):
        if not data:
            return False
        choice = data.get(str(self.pk), None)
        if choice is None:
            return False
        return self.get_instance().validate_choice(choice)

    def _serialize_condition(self, _):
        """Convert an answer into a lookup key, if applicable

        This is only applicable if `branching_possible` is True.
        """
        raise NotImplementedError

    def generate_canned_text(self, data):
        answer = deepcopy(data.get(str(self.pk), {}))  # Very explicitly work on a copy
        choice = answer.get('choice', None)
        canned = ''
        if choice:
            canned = self.get_instance().get_canned_answer(choice)
        answer['text'] = canned
        return answer

    def get_canned_answer(self, answer, frame=None, **kwargs):
        if not self.canned_answers.exists():
            return ''

        if not answer:
            return ''

        if self.canned_answers.count() == 1:
            return self.canned_answers.get().canned_text

        choice = self._serialize_condition(answer)
        canned = self.canned_answers.filter(choice=choice)
        if canned:
            return canned[0].canned_text or answer
        return ''

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
        questions = {str(q.pk): q for q in (Question.objects
                                            .select_related('node')
                                            .filter(pk__in=answers.keys())) }
        for question_pk, answer in answers.items():
            q = questions[question_pk]
            if not q.node: continue
            q = q.get_instance()
            condition = q.map_choice_to_condition(answer)
            data[str(q.node.slug)] = condition
        return data

    def get_first_question_in_next_section(self):
        next_section = self.section.get_next_section()
        while next_section:
            if next_section.questions.exists():
                return next_section.first_question
            next_section = next_section.get_next_section()
        return None

    def get_last_question_in_prev_section(self):
        prev_section = self.section.get_prev_section()
        while prev_section:
            if prev_section.questions.exists():
                return prev_section.last_question
            prev_section = prev_section.get_prev_section()
        return None

    def get_all_following_questions(self):
        "Return a qs of all questions in the same section with higher pos"
        return Question.objects.filter(section=self.section, position__gt=self.position)

    def get_potential_next_questions_with_edge(self):
        """Return a set of potential next questions

        Format: a set of tuples (type, question) where ``type`` is a string:

        "->": No node, question next in order by position
        "=>": Node but no edges, question next in order by position
        string: Edge condition or CannedAnswer legend
        """
        all_following_questions = self.get_all_following_questions()
        if not all_following_questions.exists():
            return set()
        if not self.node:
            return set([('->', all_following_questions[0])])
        edges = self.node.next_nodes.all()
        if not edges:
            return set([('=>', all_following_questions[0])])
        next_questions = []
        for edge in edges:
            edge_payload = getattr(edge, 'payload', None)
            condition = edge.condition
            if edge_payload:
                condition = str(getattr(edge_payload, 'legend', condition))
            node_payload = getattr(edge.next_node, 'payload', None)
            next_questions.append((condition, node_payload))
        next_questions = set(next_questions)
        return next_questions

    def get_potential_next_questions(self):
        "Return a set of potential next questions"
        next_questions = self.get_potential_next_questions_with_edge()
        return set(v for c, v in next_questions)

    def get_next_question(self, answers=None, in_section=False):
        following_questions = self.get_all_following_questions()
        if not following_questions.exists():
            return self.get_first_question_in_next_section()

        if not self.node:
            return following_questions[0]

        if self.node.end and not in_section:
            # Break out of section because fsa.end == True
            return self.get_first_question_in_next_section()

        if not self.node.next_nodes.exists():
            return following_questions[0]

        data = self.map_answers_to_nodes(answers)
        next_node = self.node.get_next_node(data)
        if next_node:
            # Break out of section because fsa.end == True
            if next_node.end and not in_section:
                return self.get_first_question_in_next_section()
            # Not at the end, get payload
            try:
                return next_node.payload
            except Question.DoesNotExist:
                raise TemplateDesignError('Error in template design: next node ({}) is not hooked up to a question'.format(next_node))

        return None

    def get_all_preceding_questions(self):
        "Return a qs of all questions in the same section with lower pos"
        return Question.objects.filter(section=self.section, position__lt=self.position)

    def get_potential_prev_questions(self):
        preceding_questions = self.get_all_preceding_questions()
        if not preceding_questions.exists():
            return ()

        prev_pos_question = list(preceding_questions)[-1]
        if prev_pos_question.obligatory:
            return (prev_pos_question,)
        all_prev_oblig_questions = preceding_questions.filter(obligatory=True)
        if not all_prev_oblig_questions.exists():
            return ()
        prev_oblig_question = list(all_prev_oblig_questions)[-1]
        return preceding_questions.filter(position__gte=prev_oblig_question.position)

    def get_prev_question(self, answers=None, in_section=False):
        preceding_questions = self.get_potential_prev_questions()
        if not preceding_questions:
            if not in_section:
                return self.get_last_question_in_prev_section()
            return None

        if len(preceding_questions) == 1:
            return list(preceding_questions)[0]

        # Walk forward from previous obligatory question
        if not self.node or self.node.start:
            return list(preceding_questions)[-1]

        data = self.map_answers_to_nodes(answers)
        prev_node = self.node.get_prev_node(data)
        if prev_node:
            try:
                return prev_node.payload
            except Question.DoesNotExist:
                raise TemplateDesignError('Error in template design: prev node ({}) is not hooked up to a question'.format(prev_node))

        return list(preceding_questions)[-1]

    def is_last_in_section(self):
        if not self.get_all_following_questions().exists():
            return True
        if self.node:
            if self.node.end:
                return True
#             next_nodes = self.node.next_nodes.all()
#             if next_nodes:
# 
#                 return True
        return False

#     def get_next_via_path


    def frame_canned_answer(self, answer, frame=True):
        result = answer
        if frame and self.framing_text:
            result = self.framing_text.format(answer)
        return mark_safe(result)


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

    def is_valid(self):
        canned_answers = self.canned_answers.values_list('choice', flat=True)
        if set(canned_answers) == set(('Yes', 'No')):
            return True
        return False

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

    def get_choices(self):
        choices = (
            (True, 'Yes'),
            (False, 'No'),
        )
        return choices

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if choice is None:
            return False
        if choice in self.get_choices_keys():
            return True
        return False


class ChoiceQuestion(Question):
    "A branch-capable question answerable with one of a small set of choices"
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'choice'
        super().save(*args, **kwargs)

    def is_valid(self):
        if self.canned_answers.count() > 1:
            return True
        return False

    def _serialize_condition(self, answer):
        """
        Return answer unchanged
        """
        return answer

    def get_choices(self):
        choices = self.canned_answers.values_list('choice', 'canned_text')
        fixed_choices = []
        for (k, v) in choices:
            if not v:
                v = k
            fixed_choices.append((k, v))
        return tuple(fixed_choices)

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if not choice:
            return False
        choices = self.get_choices_keys()
        if choice in choices:
            return True
        return False


class MultipleChoiceOneTextQuestion(Question):
    "A non-branch-capable question answerable with one or more of a small set of choices"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multichoiceonetext'
        super().save(*args, **kwargs)

    def is_valid(self):
        if self.canned_answers.count() > 1:
            return True
        return False

    def get_canned_answer(self, answer, frame=True, **kwargs):
        """
        answer = ['list', 'of', 'answers']
        """

        if not answer:
            return ''

        if len(answer) == 1:
            return self.frame_canned_answer(answer[0], frame)

        joined_answer = '{} and {}'.format(', '.join(answer[:-1]), answer[-1])
        return self.frame_canned_answer(joined_answer, frame)

    def pprint(self, value):
        return pprint_list(value['choice'])

    def get_choices(self):
        choices = tuple(self.canned_answers.values_list('choice', 'choice'))
        return choices

    def validate_choice(self, data):
        choice = set(data.get('choice', []))
        if not choice:
            return False
        choices = set(self.get_choices_keys())
        if choice <= choices:
            return True
        return False


class DateRangeQuestion(NoCheckMixin, Question):
    "A non-branch-capable question answerable with a daterange"

    DEFAULT_FRAMING_TEXT = 'From {start} to {end}'

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
        if not daterange:
            return ''

        framing_text = self.framing_text or self.DEFAULT_FRAMING_TEXT
        return framing_text.format(**daterange)

    def pprint(self, value):
        return self.framing_text.format(**value['choice'])

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if not choice:
            return False
        if choice.get('start', False) and choice.get('end', False):
            return True
        return False


class ReasonQuestion(NoCheckMixin, SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    has_notes = False

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'reason'
        super().save(*args, **kwargs)


class PositiveIntegerQuestion(NoCheckMixin, SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with a positive integer"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'positiveinteger'
        super().save(*args, **kwargs)


class EEStoreMixin:

    def is_valid(self):
        if self.eestore:
            return True
        return False

    def get_entries(self, eestore_pids):
        all_entries = self.eestore.get_cached_entries()
        entries = all_entries.filter(eestore_pid__in=eestore_pids)
        return entries

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        return self.get_canned_answer(value['choice'], frame=False)

    def get_choices(self):
        if self.eestore.sources.exists():
            sources = self.eestore.sources.all()
        else:
            sources = self.eestore.eestore_type.sources.all()
        qs = EEStoreCache.objects.filter(source__in=sources)
        choices = qs.values_list('eestore_pid', 'name')
        return choices


class ExternalChoiceQuestion(EEStoreMixin, Question):
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

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return ''

        answers = self.get_entries([choice])
        if not answers:
            return ''
        answer = answers[0]
        return self.frame_canned_answer(answer.name, frame)

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if not choice:
            return False
        choices = self.get_choices_keys()
        if choice in choices:
            return True
        return False


class ExternalChoiceNotListedQuestion(EEStoreMixin, Question):
    """A branch-capable question answerable with a single choice

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStorePluginMount`. This is used when there are
    too many for a standard multiselect.

    If the user chooses "Not listed", which is a CannedAnswer, it is possible
    to branch.
    """
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'extchoicenotlisted'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice_dict, frame=True, **kwargs):
        """
        choice = {
            'choices': 'answer',
            'not-listed': bool()
        }
        """
        if not choice_dict:
            return ''

        choice = choice_dict.get('choices', '')
        notlisted = choice_dict.get('not-listed', False)
        answer = ''

        if choice:
            answers = self.get_entries([choice])
            if answers:
                answer = self.frame_canned_answer(answers[0], frame)

        notlisted_string = ''
        if notlisted:
            canned_answer = super().get_canned_answer('not-listed', **kwargs)
            if canned_answer and canned_answer != 'not-listed':
                notlisted_string = canned_answer

        out = list(filter(None, (answer, notlisted_string)))
        if out:
            return mark_safe(' '.join(out))
        return mark_safe('')


    def map_choice_to_condition(self, answer):
        """Convert the `choice` in an answer to an Edge.condition

        The choice is unwrapped from its structure, and set to empty if the
        question type cannot branch.
        """
        choice = {}
        if self.branching_possible:
            # The choice is used to look up an Edge.condition
            choice = answer.get('choice', {})
        condition = str(choice.get('not-listed', False))
        return condition

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if not answer:
            return False
        choice = answer.get('choices', '')
        not_listed = answer.get('not-listed', False)
        choices = self.get_choices_keys()
        if choice in choices or not_listed:
            return True
        return False


class ExternalMultipleChoiceOneTextQuestion(EEStoreMixin, Question):
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

    def get_canned_answer(self, choice, frame=True, **kwargs):
        """
        choice = ['list', 'of', 'answers']
        """
        if not choice:
            return ''

        answers = self.get_entries(choice)

        if not answers: # Prevent 500 if the EE cache is empty
            return ''

        out = []
        for answer in answers:
            name = answer.name
            url = answer.uri
            entry = name
            if url:
                entry = print_url({'url': url, 'name': name})
            out.append(entry)

        if len(out) == 1:
            canned_answer = out[0]
        else:
            canned_answer = '{} and {}'.format(', '.join(out[:-1]), out[-1])
        canned_answer = mark_safe(canned_answer)
        return self.frame_canned_answer(canned_answer, frame)

    def validate_choice(self, data):
        choice = data.get('choice', [])
        if not choice:
            return False
        choices = set(self.get_choices_keys())
        if choices.issuperset(choice):
            return True
        return False


class ExternalMultipleChoiceNotListedOneTextQuestion(EEStoreMixin, Question):
    """A branch-capable question answerable with multiple choices

    The choices are fetched and cached from an EEStore via an
    `easydmp.eestore.models.EEStorePluginMount`. This is used when there are
    too many for a standard multiselect.

    If the user chooses "Not listed", which is a CannedAnswer, it is possible
    to branch.
    """
    branching_possible = True

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'extmultichoicenotlistedonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice_dict, frame=True, **kwargs):
        """
        choice = {
            'choices': ['list', 'of', 'answers'],
            'not-listed': bool()
        }
        """
        if not choice_dict:
            return ''

        choices = choice_dict.get('choices', ())
        notlisted = choice_dict.get('not-listed', False)
        answers = self.get_entries(choices)

        out = []
        for answer in answers:
            name = answer.name
            url = answer.uri
            entry = name
            if url:
                entry = print_url({'url': url, 'name': name})
            out.append(entry)

        answer = ''
        if out:
            if len(out) == 1:
                answer = out[0]
            else:
                answer = '{} and {}'.format(', '.join(out[:-1]), out[-1])
        answer = self.frame_canned_answer(answer, frame)

        notlisted_string = ''
        if notlisted:
            canned_answer = super().get_canned_answer('not-listed', **kwargs)
            if canned_answer and canned_answer != 'not-listed':
                notlisted_string = canned_answer

        out = list(filter(None, (answer, notlisted_string)))
        if out:
            return mark_safe(' '.join(out))
        return mark_safe('')

    def map_choice_to_condition(self, answer):
        """Convert the `choice` in an answer to an Edge.condition

        The choice is unwrapped from its structure, and set to empty if the
        question type cannot branch.
        """
        choice = {}
        if self.branching_possible:
            # The choice is used to look up an Edge.condition
            choice = answer.get('choice', {})
        condition = str(choice.get('not-listed', False))
        return condition

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if not answer:
            return False
        try:
            choice = set(answer.get('choices', []))
        except AttributeError:
            errormsg = 'Choice is in wrong format: pk {}, input "{}", choice {}'
            LOG.error(errormsg.format(self.pk, self.input_type, answer))
            return False
        not_listed = answer.get('not-listed', False)
        choices = set(self.get_choices_keys())
        if choice <= choices or not_listed:
            return True
        return False


class NamedURLQuestion(NoCheckMixin, Question):
    """A non-branch-capable question answerable with an url

    A name/title/description for the url is optional.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'namedurl'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return ''

        answer = print_url(choice)
        return self.frame_canned_answer(answer, frame)

    def pprint(self, value):
        url = value['choice']['url']
        name = value['choice'].get('name', None)
        if name:
            return '{url} ({name})'.format(url=url, name=name)
        return url

    def pprint_html(self, value):
        return self.get_canned_answer(value['choice'], frame=False)

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if not choice:
            return False
        if choice.get('url', False):
            return True
        return False


class MultiNamedURLOneTextQuestion(NoCheckMixin, Question):
    """A non-branch-capable question answerable with several urls

    A name/title/description per url is optional.
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multinamedurlonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return u''

        urlpairs = []
        for pair in choice:
            urlpairs.append(print_url(pair))

        if len(urlpairs) == 1:
            joined_pairs = urlpairs[0]
        else:
            joined_pairs = '{} and {}'.format(', '.join(urlpairs[:-1]), urlpairs[-1])
        return self.frame_canned_answer(joined_pairs, frame)

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices, frame=False)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if not choices:
            return False
        urls = []
        for choice in choices:
            url = choice.get('url', None)
            if url:
                return True
        return False


class MultiDMPTypedReasonOneTextQuestion(NoCheckMixin, Question):
    """A non-branch-capable question answerable several type+reason+url sets

    The url is optional.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    DEFAULT_FRAMING_TEXT = """<dl>{% for triple in choices %}
<dt>{{ triple.type }}</dt>
<dd>Because {{ triple.reason }}</dd>
{% if triple.access_url %}<dd><a href="{{ triple.access_url }}">Access instructions</a></dd>{% endif %}
{% endfor %}
</dl>
"""

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multidmptypedreasononetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return ''

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if not choices:
            return False
        triples = []
        for choice in choices:
            type_ = choice.get('type', None)
            reason = choice.get('reason', None)
            if type_ and reason:
                return True
        return False


INPUT_TYPE_MAP = {
    'bool': BooleanQuestion,
    'choice': ChoiceQuestion,
    'daterange': DateRangeQuestion,
    'multichoiceonetext': MultipleChoiceOneTextQuestion,
    'reason': ReasonQuestion,
    'positiveinteger': PositiveIntegerQuestion,
    'externalchoice': ExternalChoiceQuestion,
    'extchoicenotlisted': ExternalChoiceNotListedQuestion,
    'externalmultichoiceonetext': ExternalMultipleChoiceOneTextQuestion,
    'extmultichoicenotlistedonetext': ExternalMultipleChoiceNotListedOneTextQuestion,
    'namedurl': NamedURLQuestion,
    'multinamedurlonetext': MultiNamedURLOneTextQuestion,
    'multidmptypedreasononetext': MultiDMPTypedReasonOneTextQuestion,
}


class CannedAnswer(DeletionMixin, models.Model):
    "Defines the possible answers for a branch-capable question"
    question = models.ForeignKey(Question, related_name='canned_answers')
    position = models.PositiveIntegerField(
        default=1,
        help_text='Position in question. Just used for ordering.',
        blank=True,
        null=True,
    )
    choice = models.CharField(max_length=255,
                              help_text='Human friendly view of condition')
    canned_text = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    edge = models.OneToOneField('flow.Edge', related_name='payload', blank=True,
                           null=True, on_delete=models.SET_NULL)

    @property
    def label(self):
        return self.choice

    @lru_cache(None)
    def __str__(self):
        return '{}: "{}" {}'.format(self.question.question, self.choice, self.canned_text)

    def collect(self, using='default', **kwargs):
        collector = super().collect(self, using=using, **kwargs)
        if self.edge:
            collector.collect([self.edge])
        return collector

    def clone(self, question):
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'question', 'edge'])
        return self.__class__.objects.create(question=question, **self_dict)

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
