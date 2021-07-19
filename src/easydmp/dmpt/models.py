from collections import OrderedDict
from copy import deepcopy
from datetime import date
import os
from pathlib import Path
from textwrap import fill
from typing import Text, Any, TypedDict, MutableMapping, Type, Dict, Tuple, Set
from uuid import uuid4
import logging
import socket

import graphviz as gv  # noqa
from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase
from guardian.shortcuts import get_objects_for_user, assign_perm

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.timezone import now as tznow

from easydmp.constants import NotSet

from .errors import TemplateDesignError
from .flow import Transition, TransitionMap, dfs_paths
from .utils import DeletionMixin
from .utils import PositionUtils
from .utils import print_url
from .utils import render_from_string
from .utils import _reorder_dependent_models
from .utils import SectionPositionUtils
from .positioning import Move, get_new_index, flat_reorder

from easydmp.eestore.models import EEStoreCache, EEStoreMount
from easydmp.lib.graphviz import _prep_dotsource, view_dotsource, render_dotsource_to_file, render_dotsource_to_bytes
from easydmp.lib.models import ModifiedTimestampModel, ClonableModel
from easydmp.lib import pprint_list

"""
Question and CannedAnswer have the following API re. ExplicitBranch:

- A Question may have reverse Foreign Keys to ExplicitBranch, via
  ``forward_transitions`` and ``backward_transitions``.
- A CannedAnswer may have a OneToOneField to ExplicitBranch, via ``transition``.
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
    'storageforecast'
)
CONDITION_FIELD_LENGTH = 255


# Types

AnswerNote = Text
AnswerChoice = Any
Data = MutableMapping[str, dict]


class AnswerStruct(TypedDict):
    choice: Any
    notes: str


# Helper functions


def id_or_none(modelobj):
    if modelobj:
        return modelobj.id
    return None


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


def get_answered_questions(questions, answers):
    result = []
    for q in questions:
        if str(q.pk) in answers:
            result.append(q.pk)
    LOG.debug('get_answered_questions: %s', result)
    return Question.objects.filter(pk__in=result)


# Why not just use socket.getfqdn? Well, it's *very* complicated.
# What you get differs between OSes, distros and sysadmin practice
# and "localhost" and private addresses are useless for what we need.
def _get_net_info(name=''):
    """Attempt to get all public ip-addresses and fqdns for localhost

    Returns two lists: one of fqdns and one of ips
    """
    name = name.strip()
    if not name or name == '0.0.0.0':
        name = socket.gethostname()
    try:
        addrs = socket.getaddrinfo(name, None, 0, socket.SOCK_DGRAM, 0,
                                   socket.AI_CANONNAME)
    except socket.error:
        return None, None

    fqdns = list()
    ips = list()
    for addr in addrs:
        ip = addr[4][0]
        fqdn = addr[3]
        if fqdn:
            fqdns.append(fqdn)
        if ip:
            ips.append(ip)
    return fqdns, ips


def get_origin(origin=''):
    """Try to find a decent value for export "origin"

    From most to least explicit.
    """
    if origin:
        return origin
    settings_origin = getattr(settings, 'EASYDMP_ORIGIN', None)
    if settings_origin:
        return settings_origin
    # No explicit origin given
    # YAGNI? in case of no connection/no fqdn/public ip:
    # hash of secret key? uuid4?
    fqdns, ips = _get_net_info()
    if fqdns:
        return fqdns[0]
    if ips:
        return ips[0]
    return 'n/a'

def create_template_export_obj(template):
    """
    Create an amalgamation of all objects involved in a single template

    Suitable for instanciating non-model drf serializers.
    """
    class Obj:
        pass
    obj = Obj()
    obj.comment = ''  # Empty by default

    easydmp = Obj()
    easydmp.version = settings.VERSION
    easydmp.origin = get_origin()
    easydmp.input_types = sorted(INPUT_TYPES)

    obj.easydmp = easydmp
    obj.template = template
    obj.sections = template.sections.all()

    questions = template.questions.all()
    obj.questions = template.questions.all()
    obj.explicit_branches = ExplicitBranch.objects.filter(current_question__in=questions)
    obj.canned_answers = CannedAnswer.objects.filter(question__in=questions)
    obj.eestore_mounts = EEStoreMount.objects.filter(question__in=questions)

    return obj


# models, querysets, managers


class TemplateQuerySet(models.QuerySet):

    def is_not_empty(self):
        return self.filter(sections__questions__isnull=False).distinct()

    def publicly_available(self):
        return self.filter(published__isnull=False, retired__isnull=True)

    def has_access(self, user):
        if user.has_superpowers:
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


class Template(DeletionMixin, ModifiedTimestampModel, ClonableModel):
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=8, blank=True)
    description = models.TextField(blank=True)
    more_info = models.URLField(blank=True)
    domain_specific = models.BooleanField(default=False)
    reveal_questions = models.BooleanField(
        default=False,
        help_text='Should the questions be shown in the generated text?',
    )
    version = models.PositiveIntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)
    published = models.DateTimeField(
        blank=True, null=True,
        help_text='Date when the template was made publically available.'
    )
    retired = models.DateTimeField(
        blank=True, null=True,
        help_text='Date after which the template should no longer be used.',
    )
    locked = models.DateTimeField(
        blank=True, null=True,
        help_text='Date when the template was set read-only.',
    )

    objects = TemplateQuerySet.as_manager()

    orderable_manager = 'sections'

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

    def save(self, *args, **kwargs):
        if self.published:
            self.locked = self.published
        super().save(*args, **kwargs)

    @property
    def is_empty(self):
        return not self.questions.exists()

    @property
    def title_with_version(self):
        if self.version > 1:
            return '{} v{}'.format(self.title, self.version)
        return self.title

    def create_export_object(self):
        return create_template_export_obj(self)

    @transaction.atomic
    def _clone(self, title, version, keep_permissions=True):
        """Clone the template and give it <title> and <version>

        Also recursively clones all sections, questions, canned answers,
        EEStore mounts and ExplicitBranches."""
        assert title and version, "Both title and version must be given"
        new = self.get_copy()
        new.title = title
        new.version = version
        new.published = None
        new.retired = None
        new.locked = None
        new.set_cloned_from(self)
        new.save()

        self.clone_sections(new)
        if keep_permissions:
            copy_permissions(self, new)

        for import_metadata in self.import_metadata.all():
            import_metadata.clone(new)
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
        EEStore mounts and explicit branches"""
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

    @property
    def input_types_in_use(self):
        return sorted(set(self.questions.values_list('input_type', flat=True)))

    @property
    def is_readonly(self):
        return self.locked

    def in_use(self):
        return self.plans.exists()

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

    # END: Template movement helpers

    # START: (re)ordering sections

    def ordered_sections(self) -> list:
        "Order sections with subsections in a flat list"

        result = SectionPositionUtils.ordered_template_sections(self)
        return result

    def ordered_section_pks(self) -> list:
        sections = self.ordered_sections()
        return [obj.pk for obj in sections]

    def get_section_order(self):
        "Get a list of the pk's of topmost sections, in order"
        queryset = self.sections.filter(super_section=None)
        return SectionPositionUtils.get_order(queryset)

    def get_next_section_position(self):
        return SectionPositionUtils.get_next_position(self.sections)

    def set_section_order(self, pk_list):
        queryset = self.sections.all()
        SectionPositionUtils.set_order(queryset, pk_list)

    def reorder_sections(self, pk, movement):
        # Find immediate new location
        order = self.get_section_order()
        new_index = get_new_index(movement, order, pk)
        # Map new location to full order
        swap_with = order[new_index]
        full_order = self.ordered_section_pks()
        new_index = full_order.index(swap_with)
        # Reorder
        new_order = flat_reorder(full_order, pk, new_index)
        self.set_section_order(new_order)
        self.renumber_section_positions()

    def renumber_section_positions(self):
        """Renumber section positions

        An order with gaps like (1, 2, 7, 12) becomes (1, 2, 3, 4)
        Nested orders are flattened, so (1, 2, (1, 2)) becomes (1, 2, 3, 4)
        """
        PositionUtils.renumber_positions(self.sections, self.ordered_sections())

    # END: (re)ordering sections

    def generate_canned_text(self, data: Data):
        texts = []
        for section in self.ordered_sections():
            canned_text = section.generate_canned_text(data)
            section_dict = model_to_dict(section, exclude=('_state', '_template_cache'))
            section_dict['introductory_text'] = mark_safe(section_dict['introductory_text'])
            texts.append({
                'section': section_dict,
                'text': canned_text,
            })
        return texts

    def get_summary(self, data: Data, valid_section_ids: Tuple = ()) -> OrderedDict:
        summary = OrderedDict()
        data = deepcopy(data)  # 1/2 Make absolutely sure we're working on a copy
        for section in self.ordered_sections():
            optional_section_chosen = True
            section_summary = OrderedDict()
            for question in section.find_minimal_path(data):
                value: Dict[str, Any] = {}
                question = question.get_instance()
                answer = data.get(str(question.pk), None)
                if not answer or answer.get('choice', None) is None:
                    value['answer'] = None
                else:
                    value['answer'] = question.pprint_html(answer)
                # 2/2 Otherwise this might edit the actual plan data in memory!
                # Mutable types strike back..
                value['question'] = question
                if answer and section.get_optional_section_question() == question and answer.get('choice',
                                                                                                 None) == 'No':
                    optional_section_chosen = False
                if not section.get_optional_section_question() == question and not optional_section_chosen:
                    continue
                section_summary[question.pk] = value
            may_edit_all = section.questions.exists() and not section.branching
            summary[section.full_title()] = {
                'data': section_summary,
                'section': {
                    'valid': True if section.id in valid_section_ids else False,
                    'may_edit_all': may_edit_all,
                    'depth': section.section_depth,
                    'label': section.label,
                    'title': section.title,
                    'section': section,
                    'full_title': section.full_title(),
                    'pk': section.pk,
                    'first_question': section.first_question,
                    'introductory_text': mark_safe(section.introductory_text),
                    'comment': mark_safe(section.comment),
                }
            }
        return summary

    def list_unknown_questions(self, data):
        "Find question pks of an answer set that are unknown in this template"
        question_pks = self.questions.values_list('pk', flat=True)
        data_pks = set(int(k) for k in data)
        return data_pks.difference(question_pks)

    def find_validity_of_sections(self, data):
        valids = set(self.sections.filter(questions__optional=True).values_list('pk', flat=True))
        if not data:
            invalids = set(self.sections.values_list('pk', flat=True))
            return (valids, invalids - valids)
        invalids = set()
        for section in self.sections.all():
            if section.validate_data(data):
                valids.add(section.pk)
            else:
                invalids.add(section.pk)
        return (valids, invalids)

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


class TemplateImportMetadata(ClonableModel):
    DEFAULT_VIA = 'CLI'

    template = models.ForeignKey(Template, on_delete=models.CASCADE,
                                 related_name='import_metadata')
    origin = models.CharField(
        max_length=255,
        help_text='Where the template was imported from',
    )
    original_template_pk = models.IntegerField(
        help_text='Copy of the original template\'s primary key',
    )
    originally_cloned_from = models.IntegerField(
        blank=True,
        null=True,
        help_text='Copy of the original template\'s "cloned_from"',
    )
    originally_published = models.DateTimeField(
        blank=True, null=True,
        help_text='Copy of the original template\'s "published"'
    )
    # Avoid having an import metadata model on all template dependents
    mappings = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    # metadata for the metadata
    imported = models.DateTimeField(default=tznow)
    # URL or method
    imported_via = models.CharField(max_length=255, default=DEFAULT_VIA)

    class Meta:
        verbose_name_plural = 'template import metadata'
        indexes = [
            models.Index(fields=['original_template_pk'],
                         name='tim_lookup_original_idx')
        ]

    def __str__(self):
        return f'Template #{self.original_template_pk} @ {self.origin}'

    def natural_key(self):
        return (self.origin, self.original_template_pk)

    def _clone(self, template):
        new = self.get_copy()
        new.template = template
        new.set_cloned_from(self)
        new.save()
        return new

    def _clone_update_submapping(self, qs, mapping_name):
        submapping = self.mappings.get(mapping_name, {})
        new_submapping = {}
        for orig_id, new_id in submapping.items():
            obj = qs.get(cloned_from=new_id)
            new_submapping[orig_id] = obj.id
        self.mappings[mapping_name] = new_submapping

    @transaction.atomic
    def _clone_update_all_submappings(self):
        self._clone_update_submapping(self.template.sections, 'sections')
        self._clone_update_submapping(self.template.questions, 'questions')
        self._clone_update_submapping(
            CannedAnswer.objects.filter(question__in=self.template.questions),
            'canned_answers',
        )
        self._clone_update_submapping(
            ExplicitBranch.objects.filter(current_question__in=self.template.questions),
            'explicit_branches',
        )
        self.save()

    @transaction.atomic
    def clone(self, template):
        "Make a complete copy of the import metadata and put it on <template>"
        new = self._clone(template)
        new._clone_update_all_submappings()
        return new


class SectionManager(models.Manager):
    def get_by_natural_key(self, template, position, super_section=None):
        return self.get(template=template, super_section=super_section, position=position)


class Section(DeletionMixin, ModifiedTimestampModel, ClonableModel):
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
    __LOG = logging.getLogger(__name__ + '.Section')
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
        editable=False,
    )
    introductory_text = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    super_section = models.ForeignKey('self', on_delete=models.CASCADE,
                                      null=True, blank=True,
                                      related_name='subsections')
    section_depth = models.PositiveSmallIntegerField(default=1)
    branching = models.BooleanField(default=False)
    optional = models.BooleanField(default=False,
                                   help_text='True if this section is optional. The template designer needs to provide a wording to an automatically generated yes/no question at the start of the section.')
    repeatable = models.BooleanField(default=False,
                                     help_text='True if this section is repeatable. This means a plan can have multiple answersets for this section.')

    objects = SectionManager()

    orderable_manager = 'subsections'

    class Meta:
        constraints = [
             models.UniqueConstraint(fields=('template', 'title'), name='dmpt_section_unique_title_per_template'),
             models.UniqueConstraint(fields=('template', 'position'), name='dmpt_section_unique_position_per_template'),
        ]

    def __str__(self):
        return '{}: {}'.format(self.template.title, self.full_title())

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Toggle the existence of an optional question according to self.optional
            do_section_question = BooleanQuestion.objects.filter(section=self, position=0)
            if self.optional:
                if not do_section_question:
                    self.branching = True
                    super().save(*args, **kwargs)
                    self._make_do_section_question()
            elif do_section_question:
                do_section_question.delete()
            super().save(*args, **kwargs)

    def natural_key(self):
        return (self.template, self.position, self.super_section)

    @property
    def is_readonly(self):
        return self.template.is_readonly

    def in_use(self):
        return self.template.plans.exists()

    def _make_do_section_question(self):
        """
        Automatically add a bool question with branch and add first

        If this question is answered "No", skip the section.
        """
        text_to_update = "(Template designer please update)"
        help_text = (text_to_update + 'This is an optional section. '
                     'If you select "No", this section will be skipped.')
        do_section_question = BooleanQuestion(section=self,
                                              question=text_to_update,
                                              help_text=help_text,
                                              position=0)
        do_section_question.save()
        yes = CannedAnswer(question=do_section_question, canned_text='Yes', choice='Yes')
        yes.save()
        no = CannedAnswer(question=do_section_question, canned_text='No', choice='No')
        no.save()
        branch_past_section = ExplicitBranch(current_question=do_section_question, category='Last', condition='No')
        branch_past_section.save()

    def full_title(self):
        if self.label:
            return '{} {}'.format(self.label, self.title)
        return self.title

    @transaction.atomic
    def clone(self, template, super_section=None):
        """Make a complete copy of the section and put it in <template>

        Copies questions, canned answers, EEStore mounts and  explicitbranches.
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
        return new

    @transaction.atomic
    def _clone_transitions(self, question_mapping):
        eb_mapping = {}
        ca_mapping = {}
        for old, new in question_mapping.items():
            if not old.forward_transitions.exists():
                continue
            for eb in old.forward_transitions.all():
                next_question = question_mapping.get(eb.next_question, None)
                new_eb = eb.clone(new, next_question)
                eb_mapping[eb] = new_eb
            for ca in old.canned_answers.filter(transition__isnull=False):
                ca_mapping[ca] = new.canned_answers.get(choice=ca.choice)
        for old, new in ca_mapping.items():
            new.transition = eb_mapping[old.transition]
            new.save()

    # START: (re)ordering sections

    def ordered_sections(self) -> list:
        "Order sections with subsections in a flat list"

        result = SectionPositionUtils.ordered_section_subsections(self)
        return result

    def ordered_section_pks(self) -> list:
        sections = self.ordered_sections()
        return [obj.pk for obj in sections]

    def get_section_order(self):
        "Get a list of the pk's of topmost subsections, in order"
        queryset = self.subsections
        return SectionPositionUtils.get_order(queryset)

    def get_next_section_position(self):
        return self.template.get_next_section_position()

    def set_section_order(self, pk_list):
        self.template.set_section_order(pk_list)

    def reorder_sections(self, pk, movement):
        # Find immediate new location
        order = self.get_section_order()
        new_index = get_new_index(movement, order, pk)
        # Map new location to full order
        full_order = self.template.ordered_section_pks()
        swap_with = order[new_index]
        new_index = full_order.index(swap_with)
        # Reorder
        new_order = flat_reorder(full_order, pk, new_index)
        self.template.set_section_order(new_order)
        self.template.renumber_section_positions()

    def renumber_section_positions(self):
        """Renumber section positions

        An order with gaps like (1, 2, 7, 12) becomes (1, 2, 3, 4)
        Nested orders are flattened, so (1, 2, (1, 2)) becomes (1, 2, 3, 4)
        """
        self.template.renumber_section_positions()

    # END: (re)ordering sections

    # START: (re)ordering questions

    def get_question_order(self):
        "Get a list of the pk's of questions, in order"
        return PositionUtils.get_order(self.questions)

    def set_question_order(self, pk_list):
        PositionUtils.set_order(self.questions, pk_list)

    def reorder_questions(self, pk, movement):
        _reorder_dependent_models(pk, movement, self.get_question_order,
                                  self.set_question_order)

    def renumber_question_positions(self):
        """Renumber question positions so that all are adajcent

        Eg. (1, 2, 7, 12) becomes (1, 2, 3, 4).
        """
        questions = self.questions.order_by('position')
        PositionUtils.renumber_positions(self.questions, questions)

    # END: (re)ordering questions

    # START: Section movement helpers
    #
    # Several of these are here because a name is easier to type correctly,
    # read, understand, remember and grep for than a long Django queryset dot
    # after dot structure. There are also a lot more variables then necessary,
    # to better facilitate the use of pdb. "Improve" at your own peril!

    def questions_between(self, start, end=None):
        questions = self.questions.filter(position__gt=start.position)
        if end:
            questions = questions.filter(position__lt=end.position)
        return questions

    def is_answered(self, answers: Data):
        answer = answers.get(str(self.pk), None)
        return bool(answer)

    @property
    def first_question(self):
        """Get first question in *this* section

        First questions are always on_trunk and always safe to jump to.
        """
        if self.questions.exists():
            return self.questions.order_by('position')[0]
        return None

    @property
    def last_question(self):
        """Get last question in *this* section

        This method is here for completeness. It is usually better to use
        `last_on_trunk_question` since that must be visited in any case.
        """
        if self.questions.exists():
            return self.questions.order_by('-position')[0]
        return None

    @property
    def last_on_trunk_question(self):
        """Get last *on_trunk* question in *this* section

        This is a better question to jump backwards to than `last_question`
        since that might be a question in a branch (not on_trunk), which an
        end-user might not ever visit due to branching.
        """
        qs = self.questions.filter(on_trunk=True)
        if qs.exists():
            return qs.order_by('-position')[0]
        return None

    def get_all_next_sections(self):
        return Section.objects.filter(template=self.template,
                                      position__gt=self.position)

    def get_next_section(self):
        """Get the next section after *this* one

        This method is here for completeness. It is usually better to use
        `get_next_nonempty_section` since that must be visited in any case.
        """
        next_sections = self.get_all_next_sections().order_by('position')
        if next_sections.exists():
            return next_sections[0]
        return None

    def get_next_nonempty_section(self):
        """Get the next nonempty section after *this* one

        This is a better section to jump to than `get_next_section` since it
        always contains questions and must eventually be visited anyway.
        """
        next_sections = (self.get_all_next_sections()
                         .filter(questions__isnull=False)
                         .order_by('position'))
        if next_sections.exists():
            return next_sections.first()
        return None

    def get_all_prev_sections(self):
        return Section.objects.filter(template=self.template,
                                      position__lt=self.position)

    def get_prev_section(self):
        """Get the previpus section before *this* one

        This method is here for completeness. It is usually better to use
        `get_prev_nonempty_section` since that must be visited in any case.
        """
        prev_sections = self.get_all_prev_sections().order_by('-position')
        if prev_sections.exists():
            return prev_sections[0]
        return None

    def get_prev_nonempty_section(self):
        """Get the prevous nonempty section before *this* one

        This is a better section to jump to than `get_prev_section` since it
        always contains questions and must eventually be visited anyway.
        """
        prev_sections = (self.get_all_prev_sections()
                         .filter(questions__isnull=False)
                         .order_by('-position'))
        if prev_sections.exists():
            return prev_sections[0]
        return None

    def get_first_question_in_next_section(self):
        """Get first question in *the next nonempty* section

        These are always on_trunk and always safe to jump to.
        """
        next_section = self.get_next_nonempty_section()
        if next_section:
            next_question = next_section.questions.order_by('position')[0]
            self.__LOG.debug('get_first_question_in_next_section: found: #%i', next_question.id)
            return next_question
        self.__LOG.debug('get_first_question_in_next_section: last quesdtion in template')
        return None

    def get_last_question_in_prev_section(self):
        """Get last question in *the previous nonempty* section

        This method is here for completeness. It is always better to use
        `get_last_on_trunk_question_in_prev_section()` since that must be
        visited in any case.
        """
        prev_section = self.get_prev_nonempty_section()
        if prev_section:
            return prev_section.last_question
        return None

    def get_last_on_trunk_question_in_prev_section(self):
        """Get last *on_trunk* question in *the previous nonempty* section

        This is a better question to jump backwards to than
        `get_last_question_in_prev_section()` since that might be a question in
        a branch (not on_trunk), which an end-user might not ever visit due to
        branching.
        """
        prev_section = self.get_prev_nonempty_section()
        if prev_section:
            return prev_section.last_on_trunk_question
        return None

    def get_last_answered_question_in_prev_section(self, answers):
        """Get last *on_trunk* question in *the previous nonempty* section

        This is a better question to jump backwards to than
        `get_last_question_in_prev_section()` since that might be a question in
        a branch (not on_trunk), which an end-user might not ever visit due to
        branching.
        """
        prev_section = self.get_prev_nonempty_section()
        if prev_section:
            self.__LOG.debug('get_last_answered_question_in_prev_section: prev section is nonempty')
            result = prev_section.get_last_answered_question(answers)
            return result
        self.__LOG.debug('get_last_answered_question_in_prev_section: no suitable prev sections')
        return None

    def get_topmost_section(self):
        obj = self
        while obj.super_section is not None:
            obj = obj.super_section
        return obj

    def get_answered_questions(self, answers):
        return get_answered_questions(self.questions.all(), answers)

    def get_last_answered_question(self, answers):
        questions = self.get_answered_questions(answers)
        if not questions.exists():
            self.__LOG.debug('get_last_answered_question: nothing answered')
            return None
        last = self._get_last_answered_on_trunk_question(answers)
        end = questions.order_by('position').last().get_instance()
        if last:
            if last == end:
                self.__LOG.debug('get_last_answered_question: found: #%i',
                                 last.id)
                return last
            self.__LOG.debug('get_last_answered_question: walking forward')
            result = last._walk_forward_to_last_answered(last, answers)
            return result
        self.__LOG.debug('get_last_answered_question: not found')
        return None

    def get_on_trunk_questions(self):
        return self.questions.filter(on_trunk=True)

    def _get_last_answered_on_trunk_question(self, answers):
        qs_on_trunk = self.get_on_trunk_questions()
        if not qs_on_trunk.exists():
            # Empty section, so no on_trunk questions
            return None

        # Find the answered on_trunk question with the last position
        answered = get_answered_questions(qs_on_trunk, answers)
        if answered:
            last = tuple(answered)[-1]
            return last

    # END: Section movement helpers

    def get_optional_section_question(self):
        if self.optional:
            return self.questions.get(position=0).get_instance()
        return None

    def is_skipped(self, data):
        if not self.optional:  # Non-optional sections can never be skipped
            return False
        toggle_question = self.get_optional_section_question()
        toggle_answer = toggle_question.get_answer_choice(data)
        if not data or not toggle_answer:
            return True  # Should simplify logic elsewhere
        toggle = toggle_question._serialize_condition(toggle_answer)
        if toggle == 'No':
            return True
        return False

    def generate_canned_text(self, data: Data):
        texts = []
        questions = self.questions.order_by('position')
        if self.is_skipped(data):
            questions = [self.get_optional_section_question()]
        else:
            questions = questions.filter(position__gt=0)
        for question in questions:
            answer = question.get_instance().generate_canned_text(data)
            if not isinstance(answer.get('text', ''), bool):
                texts.append(answer)
        return texts

    def get_data_summary(self, data: Data):
        data = deepcopy(data)  # 1/2 Make absolutely sure we're working on a copy
        data_summary = OrderedDict()
        optional_section_chosen = True
        for question in self.find_minimal_path(data):
            value: Dict[str, Any] = {}
            question = question.get_instance()
            answer = data.get(str(question.pk), None)
            if not answer or answer.get('choice', None) is None:
                value['answer'] = None
            else:
                value['answer'] = question.pprint_html(answer)
            # 2/2 Otherwise this might edit the actual data in memory!
            # Mutable types strike back..
            value['question'] = question
            if answer and self.get_optional_section_question() == question and answer.get('choice',
                                                                                             None) == 'No':
                optional_section_chosen = False
            if not self.get_optional_section_question() == question and not optional_section_chosen:
                continue
            data_summary[question.pk] = value
        return data_summary

    def get_meta_summary(self, **kwargs):
        "Serialize a section, suitable for using in an HTML template"

        has_questions = self.questions.exists()
        may_edit_all = has_questions and not self.branching
        summary_dict = {
            'has_questions': has_questions,
            'may_edit_all': may_edit_all,
            'depth': self.section_depth,
            'label': self.label,
            'branching': self.branching,
            'title': self.title,
            'section': self,
            'full_title': self.full_title(),
            'pk': self.pk,
            'first_question': self.first_question,
            'introductory_text': mark_safe(self.introductory_text),
            'comment': mark_safe(self.comment),
        }
        summary_dict.update(**kwargs)
        return summary_dict

    def generate_complete_path_from_data(self, data: Dict) -> Tuple[int]:
        question = self.first_question
        if not question:
            return ()
        path = []
        while question:
            qid = str(question.pk)
            if not qid in data:
                break
            path.append(qid)
            question = question.get_next_question(data, in_section=True)
        return path

    def find_validity_of_questions(self, data: Dict) -> Tuple[Set[int], Set[int], Set[int]]:
        """
        The sets of pks of Questions for which the given answer data is valid/invalid.
        """
        questions = self.questions.all()
        valids = set(questions.filter(optional=True).values_list('pk', flat=True))
        if not data:
            invalids = questions.filter(optional=False)
            return (valids, set(invalids.values_list('pk', flat=True)))
        invalids = set()
        for question in questions:
            question = question.get_instance()
            try:
                valid = question.validate_data(data)
            except AttributeError:
                valid = False
                if question.optional:
                    valid = True
            if valid:
                valids.add(question.pk)
            else:
                invalids.add(question.pk)
        return (valids, invalids)

    def validate_data(self, data, question_validity_status=()):
        if not self.questions.exists():
            return True
        if not data:
            return False
        # Toggle question == 'No' makes the section valid
        if self.is_skipped(data):
            return True
        if not question_validity_status:
            valids, invalids = self.find_validity_of_questions(data)
        else:
            valids, invalids = question_validity_status
        if not self.branching:
            if invalids:
                return False
            return True
        path = self.generate_complete_path_from_data(data)
        return self.is_valid_and_complete_path(path, valids, invalids)

    def is_valid_and_complete_path(self, path, valids, invalids) -> bool:
        if not self.is_complete_path(path):
            return False
        path = set(path)
        if valids >= path and not invalids & path:
            return True
        return False

    def is_complete_path(self, path) -> bool:
        paths = self.find_all_paths()
        if tuple(path) in paths:
            return True
        return False

    def find_minimal_path(self, data: Data=None):
        minimal_qs = self.questions.filter(on_trunk=True).order_by('position')
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

    def generate_transition_map(self, pk=True, start=None, end=None):
        assert isinstance(start, (type(None), int, Question))
        assert isinstance(end, (type(None), int, Question))
        tm = TransitionMap()
        ebs = ExplicitBranch.objects.filter(
            current_question__in=self.questions.all()
        )
        if start:
            if isinstance(start, int):
                start = Question.objects.get(pk=start)
        if end:
            if isinstance(end, int):
                end = Question.objects.get(pk=end)
        if ebs:
            if start:
                ebs = ebs.filter(
                    current_question__position__gte=start.position
                )
            if end:
                ebs = ebs.filter(
                    current_question__position__lt=end.position
                )
            for eb in ebs:
                tm.add(eb.to_transition(pk=pk))
        questions = self.questions.order_by('position')
        if start:
            questions = questions.filter(position__gte=start.position)
        if end:
            questions = questions.filter(position__lt=end.position)
        for question in questions:
            transitions = question.get_potential_next_questions_with_transitions()
            for trn in transitions:
                if pk:
                    next_question = id_or_none(trn.next)
                    current = question.pk
                else:
                    next_question = trn.next
                    current = question
                category = trn.category
                # Don't overwrite an existing branch
                if not tm.select_transition(current, trn.choice):
                    t = Transition(category, current, trn.choice, next_question)
                    tm.add(t)
        return tm

    # Start Graphviz: generate graphs to show section branching

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
                    .prefetch_related('canned_answers')
                    .order_by('position')
        ):
            q_kwargs = {}
            q_label = '{}\n<{}>'.format(question, question.input_type)
            if debug:
                on_trunk = '-' if question.on_trunk else 'N'
                optional = 'o' if question.optional else '-'
                q_label = '"{}"\n<{}>\np{} #{} {}{}'.format(
                    question,
                    question.input_type,
                    question.position,
                    question.pk,
                    on_trunk,
                    optional
                )
            q_kwargs['label'] = fill(q_label, 20)
            q_id = 'q{}'.format(question.pk)
            if question.pk == self.first_question.pk:
                dot.edge(s_start_id, q_id, **s_kwargs)
            dot.node(q_id, **q_kwargs)
            next_questions = tm.transition_map.get(question.pk, None)
            if next_questions:
                cas = question.canned_answers.all()
                for choice in next_questions:
                    category = next_questions[choice]['category']
                    next_question = next_questions[choice]['next']
                    if next_question:
                        nq_id = 'q{}'.format(next_question)
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
                            if ca.transition:
                                edge_label += ' eb{}'.format(ca.transition.pk)
                        if category in ('CannedAnswer', 'ExplicitBranch'):
                            edge_label += ': "{}"'.format(choice)
                    dot.edge(q_id, nq_id, label=fill(edge_label, 15))
            else:
                dot.edge(q_id, s_end_id)
        return dot.source

    def view_dotsource(self, format, dotsource=None, debug=False):  # pragma: no cover
        """Show graph on locally attached monitor - development only!

        This depends on the OS recognizing the format.
        """
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

    def render_dotsource_to_bytes(self, format, dotsource=None, debug=False):
        if not dotsource:
            dotsource = self.generate_dotsource(debug=debug)
        return render_dotsource_to_bytes(format, dotsource)

    def get_dotsource_filename(self, format='pdf'):
        return 'section-{}.{}'.format(self.pk, format)

    # End Graphviz: generate graphs to show section branching

class NoCheckMixin:

    def is_valid(self):
        return True


class SimpleFramingTextMixin:
    """Generate a canned answer for a non-branching, atomic type

    This includes strings, but excludes any other iterables.
    """
    def get_canned_answer(self, choice: AnswerChoice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()  # type: ignore

        choice = str(choice)
        return self.frame_canned_answer(choice, frame)  # type: ignore


class PrimitiveTypeMixin(NoCheckMixin, SimpleFramingTextMixin):
    pass


class ExplicitBranchQuerySet(models.QuerySet):

    def transitions(self, pks=False):
        transitions = set()
        for eb in self.all():
            current = eb.current_question or None
            if current:
                current = current.pk if pks else current.get_instance()
            next_question = eb.next_question or None
            if next_question:
                next_question = next_question.pk if pks else next_question.get_instance()
            condition = eb.condition or None
            transitions.add(
                Transition(eb.category, current, condition, next_question)
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
    MODERNIZED_CATEGORIES = {
        'Node-edgeless': 'position',
        'Edge': 'ExplicitBranch',
    }

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
        next_question = explicit_branch.next_question
        next_question = next_question.get_instance() if next_question else None
        if pk:
            current = id_or_none(current)
            next_question = id_or_none(next_question)
        return Transition(category, current, condition, next_question)

    def to_transition(self, pk=False):
        return self._to_transition(self, pk=pk)

    @classmethod
    def modernize_category(cls, category):
        return cls.MODERNIZED_CATEGORIES.get(category, category)


class QuestionManager(models.Manager):

    def get_by_natural_key(self, section, position):
        return self.get(section=section, position=position)


class Question(DeletionMixin, ClonableModel):
    """The database representation of a question

    Questions come in many subtypes, stored in `input_type`.

    To convert a question to its subtype, run `get_class()` for the class of an
    instance and `get_instance()` for the instance itself.

    If branching_possible is True:

    * The question *must* have at least one `CannedAnswer`

    If branching_possible is False:

    * The question need not have a `CannedAnswer`.
    * The `choice` is converted to an empty string.
    """
    __LOG = logging.getLogger(__name__ + '.Question')
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
    on_trunk = models.BooleanField(default=True)
    optional = models.BooleanField(default=False)
    optional_canned_text = models.TextField(blank=True)

    objects = QuestionManager()

    class Meta:
        unique_together = ('section', 'position')
        ordering = ('section', 'position')
        indexes = [
            models.Index(fields=['input_type', 'id']),
            models.Index(fields=['section', 'position']),
        ]

    def __str__(self):
        if self.label:
            return '{} {}'.format(self.label, self.question)
        return self.question

    def clean(self):
        # Only an optional section can have a question in position 0
        if self.position == 0:
            optional_section = getattr(self.section, 'optional', False)
            if not optional_section:  # readability counts
                raise ValidationError(
                    "Only optional sections may have a question in position 0.",
                    code='invalid',
                )

    def natural_key(self):
        return (self.section, self.position)

    @property
    def is_readonly(self):
        return self.section.is_readonly

    def in_use(self):
        return self.section.template.plans.exists()

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


    def get_next_question_position(self):
        return PositionUtils.get_next_position(self.section.questions)

    # Start: re(ordering) canned answers

    def set_canned_answer_order(self, pk_list):
        return PositionUtils.set_order(self.canned_answers, pk_list)

    def get_canned_answer_order(self):
        manager = self.canned_answers
        return PositionUtils.get_order(manager)

    def reorder_canned_answers(self, pk, movement):
        _reorder_dependent_models(pk, movement, self.get_canned_answer_order,
                                  self.set_canned_answer_order)

    def renumber_canned_answers_positions(self):
        """Renumber canned answer positions so that eg. (1, 2, 7, 12) becomes (1, 2, 3, 4)"""
        cas = self.canned_answers.order_by('position', 'pk')
        if cas.count() > 1:
            PositionUtils.renumber_positions(self.canned_answers, cas)

    # END: re(ordering) canned answers

    def is_valid(self):
        """Check that the question has been created properly

        That is: if it needs data in extra tables beyond Question, or
        information external to the system, in order to validate an answer.

        For any primitive type (str, int, dates), this is a noop.
        """
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

    def get_answer_choice(self, data: Data) -> AnswerChoice:
        choicedict = data.get(str(self.pk), {})
        return choicedict.get('choice', None)

    def validate_data(self, data: Dict) -> bool:
        """
        True if the the given data contains a valid answer for this.
        """
        if not data:
            return False
        choice = data.get(str(self.pk), None)
        valid = self.get_instance().validate_choice(choice)
        if valid:
            return True
        return False

    def _serialize_condition(self, answer: AnswerChoice) -> str:
        """Convert an answer into a lookup key

        For non-branching capable questions this is always "None"
        """
        pass

    def validate_choice(self, data: Data) -> bool:
        "Validate the input data as dependent on the input type"
        raise NotImplementedError

    def get_optional_canned_answer(self):
        if self.optional:
            return self.optional_canned_text
        return ''

    def generate_canned_text(self, data: Data):
        answer = deepcopy(data.get(str(self.pk), {}))  # Very explicitly work on a copy
        choice = answer.get('choice', None)
        canned = self.get_instance().get_canned_answer(choice)
        answer['text'] = canned
        question = str(self)
        answer['question'] = question
        return answer

    def get_canned_answer(self, choice: AnswerChoice, **kwargs) -> str:
        if not choice:
            return self.get_optional_canned_answer()

        if not self.canned_answers.exists():
            return ''

        if self.canned_answers.count() == 1:
            return self.canned_answers.get().canned_text

        choice = self.get_instance()._serialize_condition(choice)
        if choice is not None:
            canned = self.canned_answers.filter(choice=choice)
            if canned:
                return canned[0].canned_text or choice
        return ''

    def pprint(self, value: AnswerStruct):
        "Return a plaintext representation of the `choice`"
        return value['choice']

    def pprint_html(self, value: AnswerStruct):
        "Return an HTML representation of the `choice`"
        return self.pprint(value)

    def get_transition_choice(self, answer):
        if not self.branching_possible:
            return None
        choice = answer.get('choice', None)
        if choice is None:
            return None
        if isinstance(choice, list):
            return None
        return choice

    def get_condition(self, answers):
        if not answers:
            return None
        answer = answers.get(str(self.pk), None)
        if answer is None:
            return None
        q = self.get_instance()
        return q.get_transition_choice(answer)

    def get_last_answered_question_in_section(self, answers=None):
        if not self.section.questions.exists():
            return None
        last = self._get_last_answered_on_trunk_question(answers)
        if last:
            return self._walk_forward(last, None, answers)
        return None

    def is_answered(self, answers):
        answer = answers.get(str(self.pk), None)
        return bool(answer)

    def get_next_on_trunk(self):
        qs = self.section.questions.filter(on_trunk=True,
                                           position__gt=self.position)
        if not qs.exists():
            # self is or is after last on_trunk question of section
            return None
        next_on_trunk = qs.order_by('position').first()
        return next_on_trunk

    def get_all_following_questions(self):
        "Return a qs of all questions in the same section with higher pos"
        return self.section.questions.filter(position__gt=self.position)

    def get_potential_next_questions_with_transitions(self):
        """Return a set of potential next questions

        Format: a set of tuples (category, choice, question)

        "category" is a string::

        "position": No ExplicitBranch, question next in order by position
        "CannedAnswer": choice is from a CannedAnswer
        "ExplicitBranch": choice may or may not be relevant, next question from
            an ExplicitBranch
        "Last": There are no questions after this one, explicitly set
        "last": There are no questions after this one, implicitly

        "choice" is a string or None:

        string: from a CannedAnswer.legend
        None: unconditional choice

        "question" is a Question, or None in the case of "last/Last"
        """
        proper_self = self.get_instance()
        all_following_questions = self.get_all_following_questions()
        if not all_following_questions.exists():
            return set([Transition('last', proper_self, None, None)])
        # XX1
        next_by_position = all_following_questions[0].get_instance()
        next_by_position_trn = set(
            [Transition('position', proper_self, None, next_by_position)]
        )
        if self.forward_transitions.exists():
            next_in_db = self.forward_transitions.transitions()
            return next_in_db | next_by_position_trn
        return next_by_position_trn

    def get_potential_next_questions(self):
        "Return a set of potential next questions"
        next_questions = self.get_potential_next_questions_with_transitions()
        return set(v for _, _, _, v in next_questions if v)

    def generate_transition_map(self, pk=False):
        tm = TransitionMap()
        transitions = self.get_potential_next_questions_with_transitions()
        current = self.pk if pk else self.get_instance()
        for trn in transitions:
            category = trn.category
            next_question = trn.next
            if next_question:
                next_question = next_question.pk if pk else next_question.get_instance()
            t = Transition(category, current, trn.choice, next_question)
            tm.add(t)
        ebs = ExplicitBranch.objects.filter(current_question=self)
        for eb in ebs:
            t = eb.to_transition(pk=pk)
            tm.add(t)
        return tm

    def get_next_question(self, answers=None, in_section=False):
        # New system
        transition_map = self.generate_transition_map()

        condition = self.get_instance().get_condition(answers)
        transition = transition_map.select_transition(self, condition)
        if transition and transition.next:
            self.__LOG.debug('get_next_question: found: #%i', transition.next.id)
            return transition.next
        self.__LOG.debug('get_next_question: no transition.next')
        if in_section:
            self.__LOG.debug('get_next_question: last in section')
            return None
        self.__LOG.debug('get_next_question: try next sections')
        next_question = self.section.get_first_question_in_next_section()
        return next_question

    def has_prev_question(self):
        if self.get_all_preceding_questions().exists():
            self.__LOG.debug('has_prev_question: Yes')
            return True
        if self.section.get_prev_nonempty_section():
            self.__LOG.debug('has_prev_question: Yes')
            return True
        self.__LOG.debug('has_prev_question: No')
        return False

    def get_all_preceding_questions(self):
        "Return a qs of all questions in the same section with lower pos"
        return Question.objects.filter(section=self.section, position__lt=self.position)

    def get_potential_prev_questions(self):
        self.__LOG.debug('get_potential_prev_questions: for #%i', self.id)
        preceding_questions = self.get_all_preceding_questions()
        # No preceding questions
        if not preceding_questions.exists():
            self.__LOG.debug('get_potential_prev_questions: no preceding')
            return ()

        # Is the previous question on_trunk? Use that
        prev_pos_question = list(preceding_questions)[-1]
        if prev_pos_question.on_trunk:
            self.__LOG.debug('get_potential_prev_questions: prev is on_trunk: #%i',
                      prev_pos_question.id)
            return (prev_pos_question,)
        # Chcek if there are any on_trunk questions before us
        all_prev_oblig_questions = preceding_questions.filter(on_trunk=True)
        if not all_prev_oblig_questions.exists():
            self.__LOG.warn('get_potential_prev_questions: no oblig before this, bug?')
            return ()  # No preceding questions, might be bug
        # Return all questions after previous on_trunk question
        prev_oblig_question = list(all_prev_oblig_questions)[-1]
        preceding_questions = preceding_questions.filter(
            position__gte=prev_oblig_question.position
        )
        self.__LOG.debug('get_potential_prev_questions: found %i!',
                  preceding_questions.count())
        return preceding_questions

    def get_best_prev_question_in_last_section(self, answers):
        self.__LOG.debug('get_best_prev_question_in_last_section: for #%i',
                         self.id)
        last_answered = self.section.get_last_answered_question_in_prev_section(answers)
        if last_answered:
            self.__LOG.debug('get_best_prev_question_in_last_section: found, last answered: #%i',
                             last_answered.id)
            return last_answered
        last_on_trunk = self.section.get_last_on_trunk_question_in_prev_section()
        if last_on_trunk:
            self.__LOG.debug('get_best_prev_question_in_last_section: found, last on_trunk: #%i',
                             last_on_trunk.id)
            return last_on_trunk
        self.__LOG.debug('get_best_prev_question_in_last_section: last question')
        return None

    def get_prev_question(self, answers=None, in_section=False):
        """Get the best previous question, taking branching into account

        If there are no preceding questions in this section at all, return None
        if `in_section` is True, otherwise look for a question in the previous
        nonempty section.

        If there are is only one preceding question go there.

        If there is more than one preceding question, go to the correct one
        according to branching, by checking existing answers. Technically, go
        to the previous on_trunk answered question then see if any not
        on_trunk questions have been after answered that one.
        """
        self.__LOG.debug('get_prev_question: for #%i', self.id)
        preceding_questions = self.get_potential_prev_questions()
        if not preceding_questions:
            if not in_section:
                self.__LOG.debug('get_prev_question: try prev sections')
                result = self.get_best_prev_question_in_last_section(answers)
                return result
            self.__LOG.debug('get_prev_question: nothing found')
            return None

        if len(preceding_questions) == 1:
            prev = list(preceding_questions)[0]
            self.__LOG.debug('get_prev_question: found, single prev: #%i', prev.id)
            return prev

        prev = self._get_prev_question_new(answers)
        if prev:
            self.__LOG.debug('get_prev_question: found: #%i', prev.id)
            return prev
        return None

    def _get_prev_question_new(self, answers=None):
        qs_on_trunk = self.section.get_on_trunk_questions()
        answered = get_answered_questions(qs_on_trunk, answers)
        if answered:
            answered = answered.filter(position__lt=self.position)
            previous_answered = answered.order_by('-position').first()
            last = self._walk_forward(previous_answered, self.get_instance(), answers)
            return last

    @classmethod
    def _walk_forward(cls, start, end, answers):
        assert end.section == start.section
        end = end.get_instance()
        cls.__LOG.debug('_walk_forward: for #%i', start.id)
        # 1. Find all paths between start and end
        transition_map = start.section.generate_transition_map(
            pk=False,
            start=start,
            end=end,
        )
        paths = transition_map.find_paths(start, end)

        # 2. Walk forward each path until we find end
        for path in paths:
            cls.__LOG.debug('_walk_forward: try path %s', path)
            for q in path:
                try:
                    next_question = q.get_next_question(answers, in_section=True)
                    cls.__LOG.debug('_walk_forward: next: #%i', id_or_none(next_question))
                except KeyError:
                    cls.__LOG.debug('_walk_forward: question not answered')
                    continue
                if next_question not in path:  # We're on the wrong path
                    cls.__LOG.debug('_walk_forward: next not in path, try next path')
                    break
                if next_question == end:
                    cls.__LOG.debug('_walk_forward: found: #%i', id_or_none(q))
                    return q
                cls.__LOG.debug('_walk_forward: try next path')
        cls.__LOG.debug('_walk_forward: not found')
        return None

    @classmethod
    def _walk_forward_to_last_answered(cls, start, answers):
        log_prefix = '_walk_forward_to_last_answered'
        cls.__LOG.debug('_walk_forward: for #%i', start.id)

        # This is one place python could have been served by REPEAT..UNTIL
        try:
            next_question = start.get_next_question(answers, in_section=True)
        except KeyError:
            cls.__LOG.debug('%s: found, last: #%i', log_prefix, start.id)
            return start
        if next_question is None:
            cls.__LOG.debug('%s: found, last: #%i', log_prefix, start.id)
            return start

        # 1. Find all paths following start
        transition_map = next_question.generate_transition_map(
            pk=False,
        )
        paths = transition_map.find_paths(next_question)

        # 2. Walk forward each path until we find end
        for path in paths:
            cls.__LOG.debug('%s: try path %s', log_prefix, path)
            for q in path:
                try:
                    next_question = q.get_next_question(answers, in_section=True)
                    cls.__LOG.debug('%s: next: #%s', log_prefix, id_or_none(next_question))
                except KeyError:
                    cls.__LOG.debug('%s: found: #%i:', log_prefix, id_or_none(q))
                    return q
                if next_question not in path:  # We're on the wrong path
                    cls.__LOG.debug('%s: next not in path, try next path', log_prefix)
                    break
                if next_question is None:
                    cls.__LOG.debug('%s: found, last: #%i', log_prefix, id_or_none(q))
                    return q
                cls.__LOG.debug('%s: try next path', log_prefix)
        cls.__LOG.debug('%s: found, start: #%i', log_prefix, start.id)
        return start

    def frame_canned_answer(self, answer, frame=True):
        result = answer
        if frame and self.framing_text:
            result = self.framing_text.format(answer)
        return mark_safe(result)


class ChoiceValidationMixin:

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if self.optional and choice is None:
            return True
        if choice in self.get_choices_keys():
            return True
        return False


class IsSetValidationMixin:

    def validate_choice(self, data):
        choice = data.get('choice', NotSet)
        if choice or self.optional:
            return True
        return False


class NotListedMixin:

    def _serialize_condition(self, answer):
        choice = answer.get('choice', {})
        return choice.get('not-listed', False)

    def get_transition_choice(self, answer):
        choice = answer.get('choice', None)
        if choice is None:
            return None
        if choice['not-listed']:
            return 'not-listed'
        return 'False'


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

    def get_canned_answer(self, choice: AnswerChoice, frame=True, **kwargs):
        """
        answer = ['list', 'of', 'answers']
        """

        if not choice:
            return self.get_optional_canned_answer()

        if len(choice) == 1:
            return self.frame_canned_answer(choice[0], frame)

        joined_answer = '{} and {}'.format(', '.join(choice[:-1]), choice[-1])
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


class ReasonQuestion(IsSetValidationMixin, PrimitiveTypeMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    has_notes = False

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'reason'
        super().save(*args, **kwargs)


class ShortFreetextQuestion(IsSetValidationMixin, PrimitiveTypeMixin, Question):
    "A non-branch-capable question answerable with plaintext"
    has_notes = False

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'shortfreetext'
        super().save(*args, **kwargs)


class PositiveIntegerQuestion(PrimitiveTypeMixin, Question):
    "A non-branch-capable question answerable with a positive integer"

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'positiveinteger'
        super().save(*args, **kwargs)

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        if self.optional and answer is NotSet:
            return True
        try:
            value = int(answer)
        except (ValueError, TypeError):
            return False
        return value >= 0


class DateQuestion(PrimitiveTypeMixin, Question):
    """A non-branch-capable question answerable with an iso date

    Stored format: "YYYY-mm-dd"
    """

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'date'
        super().save(*args, **kwargs)

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        if self.optional and answer is NotSet:
            return True
        try:
            value = date.fromisoformat(answer)
        except ValueError:
            return False
        return True


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
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
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
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
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
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
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
    `easydmp.eestore.models.EEStoreMount`. This is used when there are
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


class StorageForecastQuestion(NoCheckMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    DEFAULT_FRAMING_TEXT = """<p>Storage forecast:</p>
<ul class="storage-estimate">{% for obj in choices %}
    <li>{{ obj.year }}: {{ obj.storage_estimate }} TiB, backup {{ obj.backup_percentage }}</li>
{% endfor %}</ul>
"""

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        self.input_type = 'storageforecast'
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
            year = choice.get('year', None)
            storage_estimate = choice.get('storage_estimate', None)
            backup_percentage = choice.get('backup_percentage', None)
            if year and storage_estimate and backup_percentage:
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
    'storageforecast': StorageForecastQuestion,
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

    objects = CannedAnswerQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['question', 'position'], name='dmpt_preferred_ca_ordering_idx'),
            models.Index(fields=['question', 'position', 'id'], name='dmpt_fallback_ca_ordering_idx'),
        ]

    @property
    def label(self):
        return self.choice

    def __str__(self):
        return '{}: "{}" {}'.format(self.question.question, self.choice, self.canned_text)

#     def save(self, *args, **kwargs):
#         super().save(*args, **kwargs)
#         self.sync_transition()

    def clone(self, question):
        new = self.get_copy()
        new.question = question
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
