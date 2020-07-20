from collections import OrderedDict
from copy import deepcopy
from functools import lru_cache
import os
from pathlib import Path
from textwrap import fill
from uuid import uuid4
import logging

import graphviz as gv  # noqa
from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase
from guardian.shortcuts import get_objects_for_user, assign_perm

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.timezone import now as tznow

from .errors import TemplateDesignError
from .flow import Transition, TransitionMap
from .utils import DeletionMixin
from .utils import RenumberMixin
from .utils import print_url
from .utils import render_from_string

from easydmp.eestore.models import EEStoreCache
from easydmp.lib.graphviz import _prep_dotsource, view_dotsource, render_dotsource_to_file
from easydmp.lib.models import ModifiedTimestampModel, ClonableModel
from easydmp.lib import pprint_list

"""
Question and CannedAnswer have the following API re. Node and Edge:

- They have nullable one to one keys to their respective Nodes and Edges, so
  that they can be designed separately from these and assigned to them later on.
- The Nodes and Edges can reach them through the reverse name "payload"
- They have a property "label" that the Node and Edge can read from
- For easy questions and answers, with no next states, a suitably minimal
  node or edge can be automatically created.
"""

LOG = logging.getLogger(__name__)
INPUT_TYPES = (
    'bool',
    'choice',
    'daterange',
    'multichoiceonetext',
    'reason',
    'shortfreetext',
    'positiveinteger',
    'date',
    'externalchoice',
    'extchoicenotlisted',
    'externalmultichoiceonetext',
    'extmultichoicenotlistedonetext',
    'namedurl',
    'multinamedurlonetext',
    'multidmptypedreasononetext',
    'multirdacostonetext',
)
CONDITION_FIELD_LENGTH = 255


def id_or_none(modelobj):
    if modelobj:
        return modelobj.id
    return None


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


def copy_user_permissions(orig, other):
    """Copy user permissions from one instance to another of the same class

    Objects must have a reverse relation to an explicit subclass of
    ``UserObjectPermissionBase``, with the ``related_name`` of the
    ``content_object``-field set to ``permissions_user``.

    Returns the number of new permissions set.
    """
    assert isinstance(other, type(orig)), "Objects must share a class"
    i = 0
    for access in orig.permissions_user.all():
        assign_perm(access.permission.codename, access.user, other)
        i += 1
    return i


def copy_group_permissions(orig, other):
    """Copy group permissions from one instance to another of the same class"

    Objects must have a reverse relation to an explicit subclass of
    ``GroupObjectPermissionBase``, with the ``related_name`` of the
    ``content_object``-field set to ``permissions_group``.

    Returns the number of new permissions set.
    """
    assert isinstance(other, type(orig)), "Objects must share a class"
    i = 0
    for access in orig.permissions_group.all():
        assign_perm(access.permission.codename, access.group, other)
        i += 1
    return i


def copy_permissions(orig, other):
    """Copy all permissions from one instance to another of the same class

    Returns the number of new permissions set.
    """
    assert isinstance(other, type(orig)), "Objects must share a class"
    new_uperms = copy_user_permissions(orig, other)
    new_gperms = copy_group_permissions(orig, other)
    return new_uperms + new_gperms


class TemplateQuerySet(models.QuerySet):

    def publicly_available(self):
        return self.filter(published__isnull=False, retired__isnull=True)

    def has_access(self, user):
        if user.is_superuser:
            return self.all()
        guardian_access = get_objects_for_user(user, 'dmpt.use_template')
        qs = self.publicly_available() | guardian_access
        return qs.distinct()

    def has_change_access(self, user):
        return get_objects_for_user(
            user,
            'dmpt.change_template',
            with_superuser=True,
        )


class Template(DeletionMixin, RenumberMixin, ModifiedTimestampModel, ClonableModel):
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=8, blank=True)
    description = models.TextField(blank=True)
    more_info = models.URLField(blank=True)
    domain_specific = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)
    published = models.DateTimeField(
        blank=True, null=True,
        help_text='Date when the template is publically available, and set read-only.'
    )
    retired = models.DateTimeField(
        blank=True, null=True,
        help_text='Date after which the template should no longer be used.',
    )

    objects = TemplateQuerySet.as_manager()

    class Meta:
        unique_together = ('version', 'title')
        permissions = (
            ('use_template', 'Can use template'),
        )

    def __str__(self):
        title = self.title
        if self.abbreviation:
            title = self.abbreviation
        if self.version > 1:
            title = '{} v{}'.format(title, self.version)
        return title

    @property
    def title_with_version(self):
        if self.version > 1:
            return '{} v{}'.format(self.title, self.version)
        return self.title

    def collect(self, **kwargs):
        collector = super().collect(**kwargs)
        if self.questions.exists():
            nodes = [q.node for q in self.questions.all() if q.node]
            fsas = set(n.fsa for n in nodes)
            collector.collect(tuple(fsas))
            edges = set()
            for n in nodes:
                edges.update(set(n.next_nodes.all() | n.prev_nodes.all()))
            collector.collect(tuple(edges))
        return collector

    @transaction.atomic
    def _clone(self, title, version, keep_permissions=True):
        """Clone the template and give it <title> and <version>

        Also recursively clones all sections, questions, canned answers,
        EEStore mounts, FSAs, nodes and edges."""
        assert title and version, "Both title and version must be given"
        new = self.get_copy()
        new.title = title
        new.version = version
        new.published = None
        new.set_cloned_from(self)
        new.save()

        self.clone_sections(new)
        if keep_permissions:
            copy_permissions(self, new)
        return new

    def clone_sections(self, new):
        # clone sections, which clones questions, canned answers, fsas and eestore mounts
        section_mapping = {}
        for section in self.sections.all():
            new_section = section.clone(new)
            section_mapping[section] = new_section
        for old_section, new_section in section_mapping.items():
            if old_section.super_section:
                new_section.super_section = section_mapping[old_section.super_section]
                new_section.save()

    def clone(self, title=None, version=1):
        """Clone the template and save it as <title>

        If <title> is not given, add a random uuid to the existing ``title``.
        The version is reset to 1 and the new template is hidden from view by
        ``published`` not being set.

        Also recursively clones all sections, questions, canned answers,
        EEStore mounts, explicit branches, FSAs, nodes and edges."""
        if not title:
            title = '{} ({})'.format(self.title, uuid4())
        new = self._clone(title=title, version=version)
        return new

    def new_version(self):
        return self._clone(title=self.title, version=self.version+1)

    def private_copy(self):
        new_title = 'Copy of "{} v{}" ({})'.format(
            self.title, self.version, tznow().timestamp()
        )
        return self.clone(title=new_title, version=self.version)

    def renumber_positions(self):
        """Renumber section positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        sections = self.sections.order_by('position')
        self._renumber_positions(sections)

    # START: Template movement helpers

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

    # END: Template movement helpers

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

    def get_summary(self, data, valid_section_ids=()):
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
                    'valid': True if section.id in valid_section_ids else False,
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
        valid_sections = set()
        invalid_sections = set()
        for section in self.sections.all():
            if section.validate_data(data):
                valid_sections.add(section.pk)
            else:
                invalid_sections.add(section.pk)
        return (valid_sections, invalid_sections)

    def set_validity_of_sections(self, plan, valids, invalids):
        plan.set_sections_as_valid(*valids)
        plan.set_sections_as_invalid(*invalids)

    def validate_data(self, data):
        assert False, data
        if not data:
            return False
        _, invalid_sections = self.find_validity_of_sections(data)
        return False if invalid_sections else True


class TemplateUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Template, on_delete=models.CASCADE,
                                       related_name='permissions_user')


class TemplateGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Template, on_delete=models.CASCADE,
                                       related_name='permissions_group')


class Section(DeletionMixin, RenumberMixin, ModifiedTimestampModel, ClonableModel):
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
    template = models.ForeignKey(Template, on_delete=models.CASCADE,
                                 related_name='sections')
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
    super_section = models.ForeignKey('self', on_delete=models.CASCADE,
                                      null=True, blank=True,
                                      related_name='subsections')
    section_depth = models.PositiveSmallIntegerField(default=1)
    branching = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            ('template', 'title'),
            ('template', 'super_section', 'position'),
        )

    @lru_cache(None)
    def __str__(self):
        return '{}: {}'.format(self.template, self.full_title())

    def full_title(self):
        if self.label:
            return '{} {}'.format(self.label, self.title)
        return self.title

    @transaction.atomic
    def clone(self, template, super_section=None):
        """Make a complete copy of the section and put it in <template>

        Copies questions, canned answers, EEStore mounts, FSAs, nodes and edges.
        """
        new = self.get_copy()
        new.template = template
        new.super_section = super_section
        new.set_cloned_from(self)
        new.save()

        question_mapping = {}
        for question in self.questions.prefetch_related(
                'forward_transitions', 'canned_answers'
        ):
            question_mapping[question] = question.clone(new)
        self._clone_transitions(question_mapping)
        self._clone_fsas(question_mapping, new)
        return new

    @transaction.atomic
    def _clone_transitions(self, question_mapping):
        eb_mapping = {}
        ca_mapping = {}
        for old, new in question_mapping.items():
            if not old.forward_transitions.exists():
                continue
            for eb in old.forward_transitions.all():
                next = question_mapping.get(eb.next_question, None)
                new_eb = eb.clone(new, next)
                eb_mapping[eb] = new_eb
            for ca in old.canned_answers.filter(transition__isnull=False):
                ca_mapping[ca] = new.canned_answers.get(choice=ca.choice)
        for old, new in ca_mapping.items():
            new.transition = eb_mapping[old.transition]
            new.save()

    @transaction.atomic
    def _clone_fsas(self, question_mapping, section):
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

    def collect(self, **kwargs):
        collector = super().collect(**kwargs)
        if self.questions.exists():
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

    # START: Section movement helpers
    #
    # Several of these are here because a name is easier to type correctly,
    # read, understand, remember and grep for than a long Django queryset dot
    # after dot structure. There are also a lot more variables then necessary,
    # to better facilitate the use of pdb. "Improve" at your own peril!

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

    # END: Section movement helpers

    def generate_canned_text(self, data):
        texts = []
        for question in self.questions.order_by('position'):
            answer = question.get_instance().generate_canned_text(data)
            if not isinstance(answer.get('text', ''), bool):
                texts.append(answer)
        return texts

    def find_validity_of_questions(self, data):
        assert data, 'No data, cannot validate'
        questions = self.questions.all()
        valids = set()
        invalids = set()
        for question in questions:
            question = question.get_instance()
            try:
                valid = question.validate_data(data)
            except AttributeError:
                valid = False
            if valid:
                valids.add(question.pk)
            else:
                invalids.add(question.pk)
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
        for path in self.find_all_paths():
            if valids == set(path):
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
        tm = self.generate_transition_map()
        graph = {}
        for transition in tm.transitions:
            graph.setdefault(transition.current, set()).add(transition.next)
        paths = []
        for path in dfs_paths(graph, self.first_question.pk):
            if not path[-1]:
                path = path[:-1]
            paths.append(tuple(path))
        return paths

    def generate_transition_map(self):
        tm = TransitionMap()
        for question in self.questions.order_by('position'):
            next_questions = question.get_potential_next_questions_with_transitions()
            for category, choice, next_question in next_questions:
                next = id_or_none(next_question)
                t = Transition(category, question.pk, choice, next)
                tm.add(t)
        return tm

    def generate_dotsource(self, debug=False):
        global gv
        dot = gv.Digraph()

        tm = self.generate_transition_map()
        section_label = 'Section "{}"'.format(self)
        if debug:
            section_label += ' p{} #{}'.format(self.position, self.id)
        dot.node('section', label=section_label, shape='plaintext')
        s_kwargs = {'shape': 'doublecircle'}
        s_start_id = 's-{}-start'.format(self.pk)
        dot.node(s_start_id, label='Start', **s_kwargs)
        with dot.subgraph() as subdot:
            subdot.attr(rank='same')
            subdot.node('section')
            subdot.node(s_start_id)
        s_end_id = 's-{}-end'.format(self.pk)
        dot.node(s_end_id, label='End', **s_kwargs)
        for question in (
                self.questions
                    .select_related('node')
                    .prefetch_related('canned_answers')
                    .order_by('position')
        ):
            node = question.node
            q_kwargs = {}
            q_label = '{}\n<{}>'.format(question, question.input_type)
            if debug:
                obligatory = '-' if question.obligatory else 'N'
                optional = 'o' if question.optional else '-'
                q_label = '"{}"\n<{}>\np{} #{} {}{}'.format(
                    question,
                    question.input_type,
                    question.position,
                    question.pk,
                    obligatory,
                    optional
                )
                if node:
                    q_label += ' n{}'.format(node.pk)
            q_kwargs['label'] = fill(q_label, 20)
            q_id = 'q{}'.format(question.pk)
            if question.pk == self.get_first_question().pk:
                dot.edge(s_start_id, q_id, **s_kwargs)
            dot.node(q_id, **q_kwargs)
            next_questions = tm.transition_map.get(question.pk, None)
            if next_questions:
                cas = question.canned_answers.all()
                for choice in next_questions:
                    category = next_questions[choice]['category']
                    next = next_questions[choice]['next']
                    if next:
                        nq_id = 'q{}'.format(next)
                    else:
                        nq_id = s_end_id
                    edge_label = category
                    if debug:
                        ca = None
                        if cas and choice:
                            try:
                                ca = cas.get(choice=choice)
                            except CannedAnswer.DoesNotExist:
                                pass
                        if ca:
                            edge_label += ' p{} #{}'.format(ca.position, ca.pk)
                            if ca.edge:
                                edge_label += ' e{}'.format(ca.edge.pk)
                    if choice:
                        edge_label += ': "{}"'.format(choice)
                    dot.edge(q_id, nq_id, label=fill(edge_label, 15))
            else:
                dot.edge(q_id, s_end_id)
        return dot.source

    def view_dotsource(self, format, dotsource=None, debug=False):  # pragma: no cover
        if not dotsource:
            dotsource = self.generate_dotsource(debug=debug)
        view_dotsource(format, dotsource, self.GRAPHVIZ_TMPDIR)

    def render_dotsource_to_file(self, format, filename, root_directory='', sub_directory='', dotsource=None, debug=False):
        if not root_directory:
            root_directory = self.GRAPHVIZ_TMPDIR
        _prep_dotsource(root_directory)
        if not dotsource:
            dotsource = self.generate_dotsource(debug=debug)
        return render_dotsource_to_file(format, filename, dotsource, root_directory, sub_directory, mode=0o755)

    def get_cached_dotsource_filename(self, format='pdf'):
        return 'section-{}.{}'.format(self.pk, format)

    def get_cached_dotsource_urlpath(self, format='pdf'):
        filename = self.get_cached_dotsource_filename(format)
        return '{}cached/dmpt/{}'.format(settings.STATIC_URL, filename)

    def refresh_cached_dotsource(self, format='pdf', debug=False):
        assert format in ('pdf', 'svg', 'dot', 'png'), 'Unsupported format: {}'.format(format)
        filename = self.get_cached_dotsource_filename(format)
        subdirectory = 'cached/dmpt'
        apppath = Path(__file__).parent.joinpath('static').resolve()
        apppath = apppath.joinpath(subdirectory)
        apppath.mkdir(mode=0o755, parents=True, exist_ok=True)
        sitepath = Path(settings.STATIC_ROOT).resolve().joinpath(subdirectory)
        sitepath.mkdir(mode=0o755, parents=True, exist_ok=True)
        filepath = apppath.joinpath(filename)
        try:
            modified = os.path.getmtime(filepath)
        except FileNotFoundError:
            modified = 0.0
        if modified < self.modified.timestamp():
            if format == 'dot':
                dotsource = self.generate_dotsource(debug=debug)
                with open(filepath, 'w') as Dotfile:
                    Dotfile.write(dotsource)
            else:
                self.render_dotsource_to_file(
                    format,
                    filename.rstrip('.'+format),
                    root_directory=apppath,
                    debug=debug
                )
            sitepath.joinpath(filename).write_bytes(filepath.read_bytes())


class NoCheckMixin:

    def is_valid(self):
        return True


class SimpleFramingTextMixin:
    """Generate a canned answer for a non-branching, atomic type

    This includes strings, but excludes any other iterables.
    """
    def get_canned_answer(self, choice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        choice = str(choice)
        return self.frame_canned_answer(choice, frame)

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if choice or self.optional:
            return True
        return False


class ExplicitBranchQuerySet(models.QuerySet):

    def transitions(self, pks=False):
        transitions = set()
        for eb in self.all():
            current = eb.current_question.pk if pks else eb.current_question
            next = eb.next_question.pk if pks else eb.next_question
            transitions.add(
                Transition(eb.category, current, eb.condition, next)
            )
        return transitions


class ExplicitBranch(DeletionMixin, models.Model):
    """
    The categories are mostly the same as what's generated by
    ``Question.get_potential_next_questions_with_transitions()``,
    except for:'position', which is the default, implicit
    transition, so we never write it into ExplicitBranch.
    """
    # camelcase categories: somehow dependent on a model
    # lowercase categories: not connected to a model
    CATEGORIES = (
        'Last',
        'CannedAnswer',
        'ExplicitBranch',
        'Edge',
        'Node-edgeless',
    )

    # XX1
    current_question = models.ForeignKey('Question', on_delete=models.CASCADE,
                                         related_name='forward_transitions')
    category = models.CharField(max_length=16, choices=zip(CATEGORIES, CATEGORIES))
    # condition: None or a string of length > 0, but Django insist on NOT NULL
    condition = models.CharField(max_length=CONDITION_FIELD_LENGTH, blank=True)
    next_question = models.ForeignKey('Question', on_delete=models.CASCADE,
                                      related_name='backward_transitions',
                                      blank=True, null=True)

    objects = ExplicitBranchQuerySet.as_manager()

    class Meta:
        unique_together = ('current_question', 'category', 'condition', 'next_question')

    def __str__(self):
        return u'{}({}): ({}, {}, {})'.format(
            self.__class__.__name__,
            id_or_none(self.current_question),
            self.category,
            force_text(self.condition),
            id_or_none(self.next_question),
        )

    def __repr__(self):
        return u'<{}>'.format(str(self))

    @transaction.atomic
    def clone(self, new_current, new_next):
        self_dict = model_to_dict(self, exclude=['id', 'pk'])
        self_dict['current_question'] = new_current
        self_dict['next_question'] = new_next
        new = self.__class__.objects.create(**self_dict)
        return new

    @classmethod
    def _to_transition(cls, explicit_branch, pk=False):
        category = explicit_branch.category
        # Django doesn't like NULLable CharFields..
        condition = explicit_branch.condition
        if not condition:
            condition = None
        current = explicit_branch.current_question.get_instance()
        current = current.get_instance() if current else None
        next_question = explicit_branch.next_question
        next_question = next_question.get_instance() if next_question else None
        if pk:
            current = id_or_none(current)
            next_question = id_or_none(next_question)
        return Transition(category, current, condition, next_question)

    def to_transition(self, pk=False):
        return self._to_transition(self, pk=pk)


class Question(DeletionMixin, RenumberMixin, ClonableModel):
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
    section = models.ForeignKey(Section, on_delete=models.CASCADE,
                                related_name='questions')
    position = models.PositiveIntegerField(
        default=1,
        help_text='Position in section. Must be unique.',
    )
    label = models.CharField(max_length=16, blank=True)
    question = models.CharField(max_length=255)
    help_text = models.TextField(blank=True)
    framing_text = models.TextField(blank=True)
    comment = models.TextField(blank=True, null=True)
    obligatory = models.BooleanField(default=True)
    optional = models.BooleanField(default=False)
    optional_canned_text = models.TextField(blank=True)
    node = models.OneToOneField('flow.Node', on_delete=models.SET_NULL,
                                blank=True, null=True, related_name='payload')

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

    def collect(self, **kwargs):
        collector = super().collect(**kwargs)
        if self.node:
            edges = set(self.node.next_nodes.all() | self.node.prev_nodes.all())
            collector.collect(tuple(edges))
            collector.collect([self.node])
        return collector

    @transaction.atomic
    def clone(self, section):
        new = self.get_copy()
        new.section = section
        new.node = None
        new.set_cloned_from(self)
        new.save()
        for ca in self.canned_answers.all():
            ca.clone(new)
        if getattr(self, 'eestore', None):
            self.eestore.clone(new)
        return new

    def renumber_positions(self):
        """Renumber canned answer positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        cas = self.canned_answers.order_by('position', 'pk')
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
        valid = self.get_instance().validate_choice(choice)
        if valid:
            return True
        return False

    def _serialize_condition(self, _):
        """Convert an answer into a lookup key, if applicable

        This is only applicable if `branching_possible` is True.
        """
        raise NotImplementedError

    def validate_choice(self, data):
        raise NotImplementedError

    def get_optional_canned_answer(self):
        if self.optional:
            return self.optional_canned_text
        return ''

    def generate_canned_text(self, data):
        answer = deepcopy(data.get(str(self.pk), {}))  # Very explicitly work on a copy
        choice = answer.get('choice', None)
        canned = self.get_instance().get_canned_answer(choice)
        answer['text'] = canned
        return answer

    def get_canned_answer(self, answer, frame=None, **kwargs):
        if not answer:
            return self.get_optional_canned_answer()

        if not self.canned_answers.exists():
            return ''

        if self.canned_answers.count() == 1:
            return self.canned_answers.get().canned_text

        choice = self.get_instance()._serialize_condition(answer)
        if choice is not None:
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
        # ExplicitBranch: not needed
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
        # ExplicitBranch: not needed
        condition = ''
        if self.branching_possible:
            # The choice is used to look up an Edge.condition
            condition = str(answer.get('choice', ''))
        return condition

    @classmethod
    def map_answers_to_nodes(self, answers):
        "Convert question pks to node pks, and choices to conditions"
        # ExplicitBranch: not needed
        data = {}
        questions = {str(q.pk): q for q in (Question.objects
                                            .select_related('node')
                                            .filter(pk__in=answers.keys()))}
        for question_pk, answer in answers.items():
            q = questions[question_pk]
            if not q.node:
                continue
            q = q.get_instance()
            condition = q.map_choice_to_condition(answer)
            data[str(q.node.slug)] = condition
        return data

    # START: Question movement helpers
    #
    # Several of these are here because a name is easier to type correctly,
    # read, understand, remember and grep for than a long Django queryset dot
    # after dot structure.

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

    def get_potential_next_questions_with_transitions(self):
        """Return a set of potential next questions

        Format: a set of tuples (category, choice, question)

        "category" is a string:

        "position": No node, question next in order by position
        "Node-edgeless": Node but no edges, question next in order by position
        "CannedAnswer": choice is from a CannedAnswer
        "Edge": choice is from an Edge
        "Last": There are no questions after this one, explicitly set
        "last": There are no questions after this one, implicitly

        "choice" is a string or None:

        string: from an Edge.condition or CannedAnswer.legend
        None: unconditional choice

        "question" is a Question, or None in the case of "last/Last"
        """
        all_following_questions = self.get_all_following_questions()
        if not all_following_questions.exists():
            return set([('last', None, None)])
        if not self.node:
            return set([('position', None, all_following_questions[0])])
        edges = self.node.next_nodes.all()
        if not edges:
            return set([('Node-edgeless', None, all_following_questions[0])])
        next_questions = []
        for edge in edges:
            edge_payload = getattr(edge, 'payload', None)
            condition = edge.condition
            category = 'Edge'
            if edge_payload:
                category = 'CannedAnswer'
                condition = str(getattr(edge_payload, 'choice', condition))
            node_payload = getattr(edge.next_node, 'payload', None)
            next_questions.append((category, condition, node_payload))
        next_questions = set(next_questions)
        return next_questions

    def get_potential_next_questions(self):
        "Return a set of potential next questions"
        next_questions = self.get_potential_next_questions_with_transitions()
        return set(v for _, _, v in next_questions if v)

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

    # XXX: ExplicitBranch: Not used
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

    # END: Question movement helpers

    def frame_canned_answer(self, answer, frame=True):
        result = answer
        if frame and self.framing_text:
            result = self.framing_text.format(answer)
        return mark_safe(result)


class ChoiceValidationMixin():

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if self.optional and choice is None:
            return True
        if choice in self.get_choices_keys():
            return True
        return False


class NotListedMixin():

    def _serialize_condition(self, answer):
        choice = answer.get('choice', {})
        return choice.get('not-listed', False)

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


class BooleanQuestion(ChoiceValidationMixin, Question):
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

    def get_choices(self):
        choices = (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )
        return choices


class ChoiceQuestion(ChoiceValidationMixin, Question):
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
        choices = self.canned_answers.order().values_list('choice', 'canned_text')
        fixed_choices = []
        for (k, v) in choices:
            if not v:
                v = k
            fixed_choices.append((k, v))
        return tuple(fixed_choices)


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
            return self.get_optional_canned_answer()

        if len(answer) == 1:
            return self.frame_canned_answer(answer[0], frame)

        joined_answer = '{} and {}'.format(', '.join(answer[:-1]), answer[-1])
        return self.frame_canned_answer(joined_answer, frame)

    def pprint(self, value):
        return pprint_list(value['choice'])

    def get_choices(self):
        choices = tuple(self.canned_answers.order().values_list('choice', 'choice'))
        return choices

    def validate_choice(self, data):
        choice = set(data.get('choice', []))
        if self.optional and not choice:
            return True
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
            return self.get_optional_canned_answer()

        framing_text = self.framing_text or self.DEFAULT_FRAMING_TEXT
        return framing_text.format(**daterange)

    def pprint(self, value):
        return self.framing_text.format(**value['choice'])

    def validate_choice(self, data):
        choice = data.get('choice', {})
        if self.optional and not choice:
            return True
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


class ShortFreetextQuestion(NoCheckMixin, SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    has_notes = False

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'shortfreetext'
        super().save(*args, **kwargs)


class PositiveIntegerQuestion(NoCheckMixin, SimpleFramingTextMixin, Question):
    "A non-branch-capable question answerable with a positive integer"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'positiveinteger'
        super().save(*args, **kwargs)


class DateQuestion(NoCheckMixin, SimpleFramingTextMixin, Question):
    """A non-branch-capable question answerable with an iso date

    Stored format: "YYYY-mm-dd"
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'date'
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


class ExternalChoiceQuestion(ChoiceValidationMixin, EEStoreMixin, Question):
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
            return self.get_optional_canned_answer()

        answers = self.get_entries([choice])
        if not answers:
            return ''
        answer = answers[0]
        return self.frame_canned_answer(answer.name, frame)


class ExternalChoiceNotListedQuestion(NotListedMixin, EEStoreMixin, Question):
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
            return self.get_optional_canned_answer()

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
            else:
                notlisted_string = 'Not found in the list'

        out = list(filter(None, (answer, notlisted_string)))
        if out:
            return mark_safe(' '.join(out))
        return mark_safe('')

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if self.optional and not answer:
            return True
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
            return self.get_optional_canned_answer()

        answers = self.get_entries(choice)

        if not answers:  # Prevent 500 if the EE cache is empty
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
        if self.optional and not choice:
            return True
        choices = set(self.get_choices_keys())
        if choices.issuperset(choice):
            return True
        return False


class ExternalMultipleChoiceNotListedOneTextQuestion(NotListedMixin, EEStoreMixin, Question):
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
            return self.get_optional_canned_answer()

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

    def validate_choice(self, data):
        answer = data.get('choice', {})
        if self.optional and not answer:
            return True
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
            return self.get_optional_canned_answer()

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
        if self.optional and not choice:
            return True
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
            return self.get_optional_canned_answer()

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
        if self.optional and not choices:
            return True
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
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            type_ = choice.get('type', None)
            reason = choice.get('reason', None)
            if type_ and reason:
                return True
        return False


class MultiRDACostOneTextQuestion(NoCheckMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    DEFAULT_FRAMING_TEXT = """<dl class="answer-cost">{% for obj in choices %}
<dt>{{ obj.title }}
{% if obj.currency_code or obj.value %}
<span>{{ obj.currency_code }} {{ obj.value|default_if_none:"Unknown" }}</span>
{% endif %}
</dt>
<dd>{{ obj.description|default:"-" }}</dd>
{% endfor %}
</dl>
"""

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'multirdacostonetext'
        super().save(*args, **kwargs)

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
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
    'shortfreetext': ShortFreetextQuestion,
    'positiveinteger': PositiveIntegerQuestion,
    'date': DateQuestion,
    'externalchoice': ExternalChoiceQuestion,
    'extchoicenotlisted': ExternalChoiceNotListedQuestion,
    'externalmultichoiceonetext': ExternalMultipleChoiceOneTextQuestion,
    'extmultichoicenotlistedonetext': ExternalMultipleChoiceNotListedOneTextQuestion,
    'namedurl': NamedURLQuestion,
    'multinamedurlonetext': MultiNamedURLOneTextQuestion,
    'multidmptypedreasononetext': MultiDMPTypedReasonOneTextQuestion,
    'multirdacostonetext': MultiRDACostOneTextQuestion,
}


class CannedAnswerQuerySet(models.QuerySet):
    def order(self):
        return self.order_by('question', 'position', 'pk')


class CannedAnswer(DeletionMixin, ClonableModel):
    "Defines the possible answers for a branch-capable question"
    question = models.ForeignKey(Question, on_delete=models.CASCADE,
                                 related_name='canned_answers')
    position = models.PositiveIntegerField(
        default=1,
        help_text='Position in question. Just used for ordering.',
        blank=True,
        null=True,
    )
    choice = models.CharField(max_length=CONDITION_FIELD_LENGTH,
                              help_text='Human friendly view of condition')
    canned_text = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    transition = models.OneToOneField(ExplicitBranch,
                                      on_delete=models.SET_NULL,
                                      blank=True, null=True,
                                      related_name='canned_answers')
    # External FSA support
    edge = models.OneToOneField('flow.Edge', on_delete=models.SET_NULL,
                                related_name='payload', blank=True, null=True)

    objects = CannedAnswerQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['question', 'position'], name='dmpt_preferred_ca_ordering_idx'),
            models.Index(fields=['question', 'position', 'id'], name='dmpt_fallback_ca_ordering_idx'),
        ]

    @property
    def label(self):
        return self.choice

    @lru_cache(None)
    def __str__(self):
        return '{}: "{}" {}'.format(self.question.question, self.choice, self.canned_text)

#     def save(self, *args, **kwargs):
#         super().save(*args, **kwargs)
#         self.sync_transition()

    def collect(self, **kwargs):
        collector = super().collect(**kwargs)
        if self.edge:
            collector.collect([self.edge])
        return collector

    def clone(self, question):
        new = self.get_copy()
        new.question = question
        new.edge = None
        new.set_cloned_from(self)
        new.save()
        return new

    def sync_transition(self):
        mangling_types = set(
            'extchoicenotlisted',
            'extmultichoicenotlistedonetext',
        )
        if self.transition and self.question.input_type not in mangling_types:
            self.transition.condition = self.choice
            self.transition.save()

    # External FSA support

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
