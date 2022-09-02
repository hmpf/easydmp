from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict, namedtuple
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from typing import Set, TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.db.models import Q, Count
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now as tznow

from easydmp.constants import NotSet
from easydmp.dmpt.forms import make_form, NotesForm
from easydmp.dmpt.export_template import create_template_export_obj
from easydmp.dmpt.models.base import get_section_meta_summary
from easydmp.dmpt.utils import DeletionMixin, make_qid
from easydmp.eventlog.utils import log_event
from easydmp.lib import dump_obj_to_searchable_string
from easydmp.lib.import_export import get_origin
from easydmp.lib.models import ClonableModel

from .utils import purge_answer
from .utils import get_editors_for_plan

if TYPE_CHECKING:
    from easydmp.auth.models import User

LOG = logging.getLogger(__name__)
GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'

AnswerSetKey = namedtuple('AnswerSetKey', ['plan', 'parent', 'section', 'identifier'])
AnswerKey = namedtuple('AnswerKey', ['answerset', 'question'])


class AnswerSetException(Exception):
    pass


def create_plan_export_obj(plan, variant, include_template=True, comment=''):
    """
    Create an amalgamation of all objects involved in a single plan

    Suitable for instanciating non-model drf serializers.
    """
    class Obj:
        pass
    obj = Obj()
    obj.comment = comment

    metadata = Obj()
    metadata.version = settings.VERSION
    metadata.origin = get_origin()
    metadata.variant = variant
    metadata.template_id = plan.template_id
    metadata.template_copy = None
    if include_template:
        metadata.template_copy = create_template_export_obj(plan.template)
    obj.metadata = metadata

    obj.plan = plan
    obj.answersets = plan.answersets.all()

    answers = Answer.objects.filter(answerset__in=obj.answersets)
    obj.answers = answers

    return obj


def _ensure_possible_answerset(section, plan, answerset_parent=None):
    error_message = None
    if plan.template != section.template:
        error_message = 'Plan "{plan}" incompatible with section "{section}"'
    elif section.super_section and answerset_parent is None:
        error_message = 'The section has a super section, but the answerset has no parent'
    if error_message:
        raise AnswerSetException(error_message)


def purge_wrongly_skipped_answersets(section, answersets):
    """Only an optional section for a plan can have a skipped answerset

    There is either one skipped answerset, or one or more unskipped answersets.
    If a section is not optional there should be *no* skipped answersets.
    """
    skipped_answersets = answersets.filter(skipped=True)

    # no skipped answersets, no problem!
    if not skipped_answersets.exists():
        return answersets

    # optional section may have only *one* skipped answerset
    if section.optional:
        if answersets.filter(skipped=None).exists():
            skipped_answersets.delete()
        elif skipped_answersets.count() > 1:
            answerset = skipped_answersets.first()  # all skipped are equal
            skipped_answersets.exclude(pk=answerset.pk).delete()
        answersets = answersets.all()
        return answersets

    # required sections cannot have *any* skipped answersets
    good_answersets = answersets.filter(skipped=None)
    if good_answersets:
        skipped_answersets.delete()
        return good_answersets

    # no visible answersets: convert one skipped answerset, delete the rest
    answerset = skipped_answersets.first()
    answerset.skipped = None
    answerset.save()
    skipped_answersets.exclude(pk=answerset.pk).delete()
    answersets = answersets.all()
    return answersets


def remove_extraneous_answersets_for_singleton_sections(section, answersets):
    """A non-repeatable section has only one answerset

    Attempt to remove any others.

    Assumes there are no extraneous skipped answersets.
    """
    if section.repeatable:  # handled elsewhere
        return answersets

    try:
        answerset = answersets.get()
        return answersets  # No multiple answersets, no problem!
    except AnswerSet.MultipleObjectsReturned:
        # Try deleting extras
        num_answersets = answersets.count()
        empties = answersets.filter(data={})
        num_empties = empties.count()
        if num_answersets > num_empties:
            empties.delete()
        elif num_answersets == num_empties:
            answerset = empties.first()
            answersets.exclude(pk=answerset.pk).delete()

        # recheck
        answersets = answersets.all()
        try:
            answerset = answersets.get()
            return answersets  # We're left with one, great!
        except AnswerSet.MultipleObjectsReturned:
            # We can't know which to delete now so panic
            raise


def fix_answersets(section, plan, answerset_parent=None):
    _ensure_possible_answerset(section, plan, answerset_parent)
    answersets = plan.get_answersets_for_section(section, answerset_parent)

    # create answerset if missing
    if not answersets.exists():
        skipped = True if section.optional else None
        AnswerSet.objects.create(
            plan=plan,
            section=section,
            parent=answerset_parent,
            skipped=skipped,
            valid=False,
        )
        answersets = answersets.all()
        return answersets

    answersets = purge_wrongly_skipped_answersets(section, answersets)
    answersets = remove_extraneous_answersets_for_singleton_sections(section, answersets)
    return answersets


def add_answerset(section, plan, answerset_parent=None):
    # must be run after fix_answersets
    # for reference, kept as code to have it checked by linters
    KARNAUGH = {
        # optional, repeatable, singleton, skipped
        (False, False, True, None): 'noop',
        (False, True, True, None): 'add',
        (True, False, True, None): 'noop',
        (True, True, True, None): 'add',
        (False, False, True, True): 'error_skipped',
        (False, True, True, True): 'convert',
        (True, False, True, True): 'convert',
        (True, True, True, True): 'convert',

        (False, False, False, None): 'error_too_many',
        (False, True, False, None): 'add',
        (True, False, False, None): 'error_too_many',
        (True, True, False, None): 'add',
        (False, False, False, True): 'error_too_many_and_skipped',
        (False, True, False, True): 'convert',
        (True, False, False, True): 'error_too_many_and_skipped',
        (True, True, False, True): 'convert',
    }
    answersets = fix_answersets(section, plan, answerset_parent)

    if not (section.repeatable and section.optional):  # noop
        return None

    if section.optional and not section.repeatable:
        answerset = answersets.get()
        if answerset.skipped:  # convert
            answerset.skipped = None
            answerset.save()
            return answerset
        return None  # noop

    if section.repeatable:  # add
        answerset = answersets.last()
        answerset = answerset.add_sibling()
        return answerset


def remove_answerset(answerset) -> None:
    # for reference, kept as code to have it checked by linters
    KARNAUGH = {
        # optional, repeatable, singleton, skipped
        (False, False, True, None): 'noop',
        (False, True, True, None): 'noop',
        (True, False, True, None): 'convert',
        (True, True, True, None): 'convert',
        (False, False, True, True): 'error_skipped',
        (False, True, True, True): 'noop',
        (True, False, True, True): 'convert',
        (True, True, True, True): 'convert',

        (False, False, False, None): 'error_too_many',
        (False, True, False, None): 'remove',
        (True, False, False, None): 'error_too_many',
        (True, True, False, None): 'remove',
        (False, False, False, True): 'error_too_many_and_skipped',
        (False, True, False, True): 'error_skipped',
        (True, False, False, True): 'error_too_many_and_skipped',
        (True, True, False, True): 'remove',
    }
    section = answerset.section
    answersets = fix_answersets(section, answerset.plan, answerset.parent)

    if not (section.repeatable and section.optional):  # noop
        return

    one_answerset = answersets.count() == 1

    if one_answerset:
        if section.optional:  # convert
            answerset.skipped = True
            answerset.save()
            return
        if section.repeatable:  # noop
            return

    answerset.delete()  # remove


class AnswerHelper():
    "Helper-class combining a Question and a Plan"

    def __init__(self, question, answerset):
        self.question = question.get_instance()
        self.answerset = answerset
        self.plan = answerset.plan
        self.answer = self.set_answer()
        # IMPORTANT: json casts ints to string as keys in dicts, so use strings
        self.question_id = str(self.question.pk)
        self.has_notes = self.question.has_notes
        self.section = self.question.section
        self.current_choice = answerset.data.get(self.question_id, {})
        self.prefix = make_qid(self.question_id)

    def get_choice(self):
        choice = self.answerset.data.get(self.question_id, {})
        if not choice:
            choice = self.answerset.previous_data.get(self.question_id, {})
        return choice

    def get_current_data(self):
        return self.answerset.data if self.answerset.data else {}

    def get_initial(self):
        return self.get_choice()

    def set_answer(self):
        answer, _ = Answer.objects.get_or_create(
            question=self.question,
            answerset=self.answerset,
            defaults={'valid': False}
        )
        return answer

    def get_form(self, **form_kwargs):
        form = make_form(self.question, **form_kwargs)
        return form

    def get_notesform(self, **form_kwargs):
        form_kwargs.pop('prefix', None)
        return NotesForm(prefix=self.prefix, **form_kwargs)

    def get_empty_bound_notesform(self):
        return NotesForm(data={'notes': ''}, prefix=self.prefix)

    def update_answer_via_forms(self, form, notesform, saved_by):
        if form.is_valid() and notesform.is_valid():
            notes = notesform.cleaned_data.get('notes', '')
            choice = form.serialize()
            choice['notes'] = notes
            return self.save_choice(choice, saved_by)
        return None

    def save_choice(self, choice, saved_by):
        LOG.debug('save_choice: q%s/p%s: Answer: previous %s current %s',
                  self.question_id, self.plan.pk, self.current_choice, choice)
        if self.current_choice != choice:
            LOG.debug('save_choice: q%s/p%s: saving changes',
                      self.question_id, self.plan.pk)
            self.plan.modified_by = saved_by
            self.answerset.update_answer(self.question_id, choice)
            self.plan.save(user=saved_by)
            self.set_valid()
            # report on change
            if choice:
                new_condition = choice.get('choice', None)
                new_answer = self.question._serialize_condition(new_condition)
                old_condition = self.current_choice.get('choice', None)
                old_answer = None
                if old_condition:
                    old_answer = self.question._serialize_condition(old_condition)
                return new_condition is not None and old_answer != new_answer
        return False

    def set_valid(self):
        if not self.answer.valid:
            LOG.debug('set_valid: q%s/p%s',
                      self.question_id, self.plan.pk)
            self.answer.valid = True
            self.answer.save()
            if not self.answerset.valid and self.section.validate_data(self.answerset.data):
                LOG.debug('set_valid: q%s/p%s: section %',
                          self.question_id, self.plan.pk, self.section.pk)
                self.answerset.valid = True
                self.answerset.save()

    def set_invalid(self):
        if self.answer.valid:
            last_validated = tznow()
            LOG.debug('set_invalid: q%s/p%s', self.question_id, self.plan.pk)
            self.answer.valid = False
            self.answer.last_validated = last_validated
            self.answer.save(update_fields=['valid', 'last_validated'])
            LOG.debug('set_invalid: q%s/p%s: section %',
                      self.question_id, self.plan.pk, self.section.pk)
            self.answerset.valid = False
            self.answerset.last_validated = last_validated
            self.answerset.save(update_fields=['valid', 'last_validated'])
            self.plan.valid = False
            self.plan.last_validated = last_validated
            self.plan.save(update_fields=['valid', 'last_validated'])


AnswerSetParentKey = namedtuple('AnswerSetParentKey', 'plan_id section_id parent_id')
AnswerSetSectionKey = namedtuple('AnswerSetSectionKey', 'plan_id section_id')


class AnswerSetQuerySet(models.QuerySet):

    def get_by_natural_key(self, plan_id, parent_id, section_id, identifier):
        return self.get(
            answerset__plan_id=plan_id,
            answerset__parent_id=parent_id,
            answerset__section_id=section_id,
            answerset__identifier=identifier,
        )

    # START: optimized answerset access

    def childmap(self, qs=None):
        mapping = defaultdict(OrderedDict)
        if not qs:
            qs = tuple(self.only('id', 'parent_id', 'section_id').iterator())
        for answerset in qs.order_by('section_id', 'parent_id', 'id'):
            mapping[answerset.parent_id][answerset.id] = answerset.section_id
        return mapping

    def plain_lookup_map(self, qs=None):
        if not qs:
            qs = self.all()
        mapping = {}
        for answerset in qs:
            mapping[answerset.id] = answerset
        return mapping

    def decorate(self, func, qs=None):
        if qs is None:
            qs = self.all()
        for answerset in qs:
            answerset.decoration = func(answerset)
        return qs

    def lookup_map(self, qs=None):
        if not qs:
            qs = self.prefetch_related('section', 'parent').order_by('pk')
        child_mapping = self.childmap(qs)
        mapping = {}
        for answerset in tuple(qs):
            parent_id = answerset.parent.pk if answerset.parent else None
            decoration = getattr(answerset, 'decoration', None)
            answersetobj = SimpleNamespace(
                children=child_mapping[answerset.id],
                answerset=answerset,
                parent_id=parent_id,
                section=answerset.section,
                decoration=decoration,
            )
            mapping[answerset.id] = answersetobj
        return mapping

    def map_by_parent_key(self, qs=None):
        if not qs:
            qs = self.all()
        mapping = defaultdict(OrderedDict)
        for answerset in qs:
            key = AnswerSetParentKey(answerset.plan_id, answerset.section_id, answerset.parent_id)
            mapping[key][answerset.id] = None
        return {k: tuple(v.keys()) for k, v in mapping.items()}

    # END: optimized answerset access


class AnswerSet(ClonableModel):
    """
    A user's set of answers to a Section
    """
    identifier = models.CharField(max_length=120, blank=True)
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='answersets')
    section = models.ForeignKey('dmpt.Section', models.CASCADE, related_name='answersets')
    parent = models.ForeignKey('self', models.CASCADE, related_name='answersets', null=True, blank=True)
    valid = models.BooleanField(default=False)
    last_validated = models.DateTimeField(auto_now=True)
    skipped = models.BooleanField(null=True, blank=True, help_text='True or None')
    # The user's answers, represented as a Question PK keyed dict in JSON.
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder, blank=True)
    previous_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder, blank=True)

    objects = AnswerSetQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('plan', 'section', 'identifier'),
                condition=Q(parent__isnull=True),
                name='plan_answerset_unique_identifiers'),
            models.UniqueConstraint(
                fields=('plan', 'section', 'parent', 'identifier'),
                condition=Q(parent__isnull=False),
                name='plan_answerset_unique_identifiers_parent'),
            models.CheckConstraint(
                check=Q(skipped=True),  # PostGreSQL: True if true OR null!
                name='plan_answerset_skipped_never_false'
            ),
        ]

    def __str__(self):
        return '"{}" #{}, section: {}, plan: {}, valid: {}'.format(
            self.identifier,
            self.pk,
            self.section_id,
            self.plan_id,
            self.valid)

    @transaction.atomic
    def save(self, importing=False, *args, **kwargs):
        if importing:
            kwargs.pop('force_insert', None)
            kwargs.pop('force_update', None)
            super().save(force_insert=True, *args, **kwargs)
            return
        self.identifier = self.get_identifier()
        super().save(*args, **kwargs)
        if not self.answers.exists():
            self.initialize_answers()

    def natural_key(self):
        return AnswerSetKey(self.plan_id, self.parent_id, self.section_id, self.identifier)

    def generate_next_identifier(self):
        # We could also have used a UUID here but they are so fugly
        count = self.__class__.objects.filter(plan=self.plan, section=self.section).count()
        return str(count + 1)

    def get_identifier(self):
        iq = self.section.identifier_question
        if not iq:
            if self.identifier:
                return self.identifier
            return self.generate_next_identifier()
        choice = self.get_choice(iq.pk)
        if choice:
            return iq.get_instance().get_identifier(choice)
        return self.generate_next_identifier()

    def add_sibling(self, identifier=None):
        if identifier is None:
            identifier = self.generate_next_identifier()
        sib = self.__class__(
            plan=self.plan,
            section=self.section,
            parent=self.parent,
            identifier=identifier,
        )
        sib.save()
        sib.add_children()
        return sib

    def get_siblings(self):
        return self.__class__.objects.filter(
            plan=self.plan,
            section=self.section,
            parent=self.parent
        ).order_by('pk')

    @transaction.atomic
    def add_children(self):
        for section in self.section.subsections.all():
            answerset, _ = AnswerSet.objects.get_or_create(plan=self.plan, section=section, parent=self)
            if answerset.answersets.exists():
                for subanswerset in answerset.answersets.all():
                    subanswerset.add_children()
            else:
                answerset.add_children()  # Cannot put this in self.save(), would loop

    # START: Traversal

    def get_next_answerset(self):
        # Children
        if self.answersets.exists():
            return self.answersets.order_by('pk').first()
        # Siblings
        siblings = tuple(self.get_siblings())
        index = siblings.index(self)
        younger = siblings[index:]
        if younger:
            return younger[0]
        # Next section
        next_section = self.section.get_next_section()
        answersets = self.plan.get_answersets_for_section(next_section)
        if answersets:
            return answersets.first()
        # We've run out of possible answersets
        return None

    def get_previous_answerset(self):
        # Siblings
        siblings = tuple(self.get_siblings())
        index = siblings.index(self)
        older = siblings[:index]
        if older:
            return older[-1]
        # Parent
        if self.parent:
            return self.parent
        # Previous section
        prev_section = self.section.get_prev_section()
        answersets = self.plan.get_answersets_for_section(prev_section)
        if answersets:
            return answersets.last()
        # We've run out of possible answersets
        return None

    # END: Traversal

    @property
    def is_empty(self):
        return bool(self.data)

    def get_answer(self, question_id):
        return self.data.get(str(question_id), {})

    @transaction.atomic
    def update_answer(self, question_id, choice, skipped=None):
        lookup_question_id = str(question_id)
        previous_choice = self.data.get(lookup_question_id, None)
        if previous_choice:
            self.previous_data[lookup_question_id] = previous_choice
        self.data[lookup_question_id] = choice
        self.answers.update_or_create(
            question_id=int(question_id),
            defaults={'valid': True}
        )
        if self.skipped != skipped:
            self.skipped = skipped
        self.save()

    def get_choice(self, question_id):
        return self.get_answer(question_id).get('choice', None)

    def get_answersets_for_section(self, section, parent=NotSet):
        return self.plan.get_answersets_for_section(section, parent)

    def delete_answers(self, question_ids, commit=True):
        deleted = set()
        for question_id in question_ids:
            str_id = str(question_id)
            if str_id in self.data:
                self.previous_data[str_id] = self.data.pop(str_id)
                deleted.add(question_id)
        if commit:
            self.save()
        LOG.debug('delete_answers: %s', deleted)
        return deleted

    def hide_unreachable_answers_after(self, question):
        """Hide any answers unreachable after this question

        First collects all questions as per branching after this question or
        until either the next on_trunk question or the final question in the
        section. Then calculates all visible questions by walking forward.
        Finally hides the invisible questions (all minus visible).

        Returns whether anything was changed.
        """
        question = question.get_instance()
        if not question.branching_possible:
            return False
        # Find any questions touched by branching
        if question.position == 0:  # optional section!
            next_question = question.get_next_question(self.data, in_section=True)
        else:
            next_question = question.get_next_on_trunk()
        between = tuple(question.section
                   .questions_between(question, next_question)
                   .values_list('id', flat=True))
        if not between:
            # Adjacent obligatories, no branch
            return False
        LOG.debug(
            'hide_unreachable_answers_after: between "%s" and %s: %s',
            question,
            '"{}"'.format(next_question) if next_question else 'end',
            between
        )
        # Collect visible questions
        show = set()
        while question != next_question:
            question = question.get_next_question(self.data, in_section=True)
            if question is None:
                # No more questions/last of section
                break
            if question.on_trunk:
                # Found next on_trunk question
                break
            show.add(question.id)
        # Hide invisible questions
        delete = set(between) - show
        hidden = self.delete_answers(delete)
        LOG.info('hide_unreachable_answers_after: Hide %s, show %s',
                 hidden or None, show or None)
        # Report whether a save is necessary
        return bool(hidden) or bool(show)

    @transaction.atomic
    def clone(self, plan, parent=None):
        # Does not clone children
        new = self.__class__.objects.create(
            plan=plan,
            section=self.section,
            data=self.data,
            previous_data=self.previous_data,
            valid=self.valid,
            parent=parent,
            last_validated=self.last_validated
        )
        # answers created during "create", fix their validity
        orig_validities = {q: valid for q, valid in
                           self.answers.values_list('question_id', 'valid')}
        for answer in new.answers.all():
            # Some old plans lack answers
            if answer.question_id in orig_validities:
                answer.valid = orig_validities[answer.question_id]
                answer.save()
        new.set_cloned_from(self)
        new.save(update_fields=['cloned_from', 'cloned_when'])
        return new

    def initialize_answers(self):
        if Answer.objects.filter(answerset=self).exists():
            return
        answers = []
        for question in self.section.questions.all():
            answers.append(Answer(question=question, answerset=self))
        Answer.objects.bulk_create(answers)

    def clean(self):
        "Remove answers to unknown questions"
        our_qids = set([
            str(qid)
            for qid in self.section.questions.values_list('id', flat=True)
        ])
        bad_data_qids = set(self.data.keys()) - our_qids
        for qid in bad_data_qids:
            del self.data[qid]
        bad_previous_data_qids = set(self.previous_data.keys()) - our_qids
        for qid in bad_previous_data_qids:
            del self.previous_data[qid]
        if bad_data_qids or bad_previous_data_qids:
            LOG.info('Removed spurious answers from answerset %s', self.id)
            self.validate()

    def validate(self, timestamp: datetime = None) -> bool:
        """
        Validates the answers and persists the validity state on this as well as on related Answers.

        Returns validity.
        """
        if self.skipped and not self.section.optional:  # in case of garbage
            self.skipped = None

        self.last_validated = timestamp or tznow()
        if self.skipped:
            valid = True
        else:
            valids, invalids, = self.section.find_validity_of_questions(self.data)
            self.set_validity_of_answers(valids, invalids)
            valid = self.section.validate_data(self.data, (valids, invalids))

            children = self.answersets.all()
            child_validity = set(
                child.validate(self.last_validated)
                for child in children if not child.skipped
            )
            valid = valid and False not in child_validity

        self.valid = valid
        self.save(update_fields=('skipped', 'valid', 'last_validated'))
        if not self.valid:
            self.plan.valid = False
            self.plan.last_validated = self.last_validated
            self.plan.save(update_fields=('valid', 'last_validated'))
        return self.valid

    def set_validity_of_answers(self, valids: Set[int], invalids: Set[int]) -> None:
        """
        Update the corresponding Answers of this with validities/invalidities given by the passed Question pks
        """
        for answer in self.answers.all():
            if answer.question.pk in valids:
                answer.valid = True
            elif answer.question.pk in invalids:
                answer.valid = False
            else:
                # answers hidden by a branch, so validity is irrelevant
                continue
            answer.save()


class AnswerQuerySet(models.QuerySet):

    def get_by_natural_key(self, answerset, question_id):
        anss = AnswerSetKey(answerset)
        return self.select_related('answerset').get(
            answerset__plan_id=anss.plan,
            answerset__parent_id=anss.parent,
            answerset__section_id=anss.section,
            answerset__identifier=anss.identifier,
            question_id=question_id,
        )


class Answer(ClonableModel):
    """
    An Answer contains metadata about an answer, such as validity. The actual answer the user gave is aggregated in
    AnswerSet.
    """
    answerset = models.ForeignKey(AnswerSet, models.CASCADE, related_name='answers')
    question = models.ForeignKey('dmpt.Question', models.CASCADE, related_name='+')
    valid = models.BooleanField(default=False)
    last_validated = models.DateTimeField(auto_now=True)

    objects = AnswerQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('answerset', 'question'),
                name='plan_answer_one_answer_per_question')
        ]

    def __str__(self):
        return f'Answer #{self.id}, q#{self.question_id}, set#{self.answerset_id}'

    def natural_key(self):
        return (tuple(self.answerset.natural_key()), self.question_id)

    def clone(self, answerset):
        new = self.__class__.objects.create(
             question=self.question,
             answerset=answerset,
             valid=self.valid,
             last_validated=self.last_validated,
        )
        new.set_cloned_from(self)
        new.save(update_fields=['cloned_from', 'cloned_when'])
        return new


class PlanQuerySet(models.QuerySet):

    def purge_answer(self, question_pk, purged_by=None):
        qs = self.all()
        for plan in qs:
            purge_answer(plan, question_pk, purged_by)

    def locked(self):
        return self.filter(locked__isnull=False)

    def unlocked(self):
        return self.filter(locked__isnull=True)

    def published(self):
        return self.filter(published__isnull=False)

    def unpublished(self):
        return self.filter(published__isnull=True)

    def valid(self):
        return self.filter(valid=True)

    def invalid(self):
        return self.exclude(valid=True)

    def editable(self, user, superpowers=True):
        if superpowers and user.has_superpowers:
            return self.all()
        return self.filter(accesses__user=user, accesses__may_edit=True)

    def viewable(self, user, superpowers=True):
        if superpowers and user.has_superpowers:
            return self.all()
        return self.filter(accesses__user=user)


class Plan(DeletionMixin, ClonableModel):
    title = models.CharField(
        max_length=255,
        help_text='''This title will be used as the title of the generated
        data management plan document. We recommend something that includes the
        name of the project the plan is for, e.g., "Preliminary data plan for
        &lt;project&gt;", "Revised data plan for &lt;project&gt;", etc.'''
    )
    abbreviation = models.CharField(
        max_length=8, blank=True,
        help_text='A short abbreviation of the plan title, for internal use. Not shown in the generated file.',
    )
    version = models.PositiveIntegerField(default=1)
    uuid = models.UUIDField(default=uuid4, editable=False)
    template = models.ForeignKey('dmpt.Template', models.CASCADE, related_name='plans')
    valid = models.BooleanField(blank=True, null=True)
    last_validated = models.DateTimeField(blank=True, null=True)
    visited_sections = models.ManyToManyField('dmpt.Section', related_name='+', blank=True)
    generated_html = models.TextField(blank=True)
    search_data = models.TextField(null=True, blank=True)
    doi = models.URLField(
        blank=True,
        default='',
        help_text='Use the URLified DOI, https://dx.doi.org/<doi>',
    )
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE,
                                 related_name='added_plans')
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE,
                                    related_name='modified_plans')
    locked = models.DateTimeField(blank=True, null=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL,
                                  blank=True, null=True,
                                  related_name='locked_plans')
    published = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL,
                                     blank=True, null=True,
                                     related_name='published_plans')

    objects = PlanQuerySet.as_manager()

    def __str__(self):
        return self.title

    def __repr__(self):
        return '{} V{} ({})'.format(self.title, self.version, self.id)

    def create_export_object(self, variant, include_template=True, comment=''):
        return create_plan_export_obj(self, variant, include_template, comment)

    def logprint(self):
        return 'Plan #{}: {}'.format(self.pk, self.title)

    @property
    def total_answers(self):
        return [answerset.data for answerset in self.answersets.all()]

    @property
    def num_total_answers(self):
        if not self.answersets.exists():
            return 0
        return sum(len(data) for data in self.total_answers)

    def question_ids_answered(self):
        out = set()
        for data in self.total_answers:
            out.update(map(int, data.keys()))
        return out

    @property
    def is_empty(self):
        if not self.answersets.exists():
            return True
        return not any(bool(answerset.data)
                       for answerset in self.answersets.all())

    # Access
    # TODO: Replace with django-guardian?

    def may_edit(self, user):
        if not user.is_authenticated:
            return False
        if self.accesses.filter(user=user, may_edit=True):
            return True
        return False

    def may_view(self, user):
        if not user.is_authenticated:
            return False
        if self.accesses.filter(user=user):
            return True
        return False

    def get_viewers(self):
        User = get_user_model()
        pas = self.accesses.exclude(may_edit=True)
        qs = User.objects.filter(plan_accesses__in=pas)
        return qs

    get_editors = get_editors_for_plan

    def add_user_to_viewers(self, user):
        ua, _ = PlanAccess.objects.update_or_create(
            user=user,
            plan=self,
            defaults={'may_edit': False})

    def add_user_to_editors(self, user):
        ua, _ = PlanAccess.objects.update_or_create(
            user=user,
            plan=self,
            defaults={'may_edit': True})

    def set_adder_as_editor(self):
        self.add_user_to_editors(self.added_by)

    # Saving, status changes

    def copy_users_from(self, oldplan):
        # TODO: needs updating if switching to django-guardian
        for pa in oldplan.accesses.all():
            pa.clone(self)

    def quiet_save(self, **kwargs):
        """Save without logging

        This is for:
        * Upgrades when the plan needs to be automatically modified.
          Instead of event logging the plan being saved, log the upgrade itself.
        * When it's necessary to save the same plan multiple times in a row
          within a short time duration, for instance because the later
          modifications depend on the plan already being saved.
        """
        if not self.pk:
            # Not for first save
            return
        super().save(**kwargs)

    def hide_unreachable_answers(self, section_qs=None):
        """Hide all unreachable answers of a plan or section"""
        if self.is_empty:
            return
        all_sections = self.template.sections.filter(
            branching=True,
            questions__isnull=False
        ).distinct()
        if not all_sections.exists():
            return
        changed = set()
        # Only work on a subset of relevant sections
        if section_qs:
            all_sections = all_sections.intersection(section_qs).distinct()
        answer_ids = self.question_ids_answered()
        for section in all_sections.order_by('position'):
            questions = section.questions.filter(on_trunk=True).order_by('position')
            # Skip unanswered sections so they don't show up in the report
            if not (answer_ids & set(questions.values_list('id', flat=True))):
                continue
            LOG.debug('hide_unreachable_answers: Section "%s" (%s)', section,
                      section.id)
            # Go, go, go
            for answerset in self.answersets.filter(section=section):
                for question in questions:
                    changed.add(self.answerset.hide_unreachable_answers_after(question))
        # Report if the plan was changed
        return any(changed)

    def save(self, user=None, question=None, recalculate=False, clone=False, importing=False, **kwargs):
        if importing:
            kwargs.pop('force_insert', None)
            kwargs.pop('force_update', None)
            super().save(force_insert=True, **kwargs)
            self.set_adder_as_editor()
            return

        if user:
            self.modified_by = user
        if not self.pk:  # New, empty plan
            super().save(**kwargs)
            if not clone:
                self.initialize_starting_answersets()
                self.set_adder_as_editor()
            LOG.info('Created plan "%s" (%i)', self, self.pk)
            template = '{timestamp} {actor} created {target}'
            log_event(self.added_by, 'create', target=self,
                      timestamp=self.added, template=template)
        else:
            self.search_data = dump_obj_to_searchable_string(self.total_answers)
            self.modified = tznow()
            if question is not None:
                # set visited
                self.visited_sections.add(question.section)
                topmost = question.section.get_topmost_section()
                if topmost:
                    self.visited_sections.add(topmost)
                # set validated
                self.validate(user, recalculate, commit=False)
            super().save(**kwargs)
            template = '{timestamp} {actor} saved {target}'
            log_event(self.added_by, 'save', target=self,
                      timestamp=self.modified, template=template)
            LOG.info('Updated plan "%s" (%i)', self, self.pk)

    @transaction.atomic
    def delete(self, user, **kwargs):
        template = '{timestamp} {actor} deleted {target}'
        log_event(user, 'delete', target=self, template=template)
        super().delete(**kwargs)

    @transaction.atomic
    def save_as(self, title, user, abbreviation='', keep_users=True, **kwargs):
        new = self.__class__(
            title=title,
            abbreviation=abbreviation,
            template=self.template,
            added_by=user,
            modified_by=user,
        )
        new.save(clone=True)
        new.clone_answersets(self)
        if keep_users:
            editors = set(self.get_editors())
            for editor in editors:
                new.add_user_to_editors(editor)
        template = '{timestamp} {actor} saved {action_object} as {target}'
        log_event(user, 'save as', target=new, object=self,
                  timestamp=new.added, template=template)
        return new

    @transaction.atomic
    def clone(self):
        new = deepcopy(self)
        new.pk = None
        new.id = None
        new.set_cloned_from(self)
        new.save(clone=True)
        new.clone_answersets(self)
        new.copy_users_from(self)
        return new

    def unset_status_metadata(self):
        self.added_by = None
        self.added = None
        self.locked_by = None
        self.locked = None
        self.modified_by = None
        self.modified = None
        self.published_by = None
        self.published = None

    @transaction.atomic
    def create_new_version(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        new = self.clone()
        new.version = self.version + 1
        new.unset_status_metadata()
        new.added_by = user
        new.added = timestamp
        new.modified_by = user
        new.modified = timestamp
        new.add_user_to_editors(user)
        if not wait_to_save:
            new.save()
        template = '{timestamp} {actor} created {target}, a new version of {action_object}'
        log_event(user, 'create new version', target=new, object=self,
                  timestamp=new.added, template=template)
        return new

    @transaction.atomic
    def unlock(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        new = self.create_new_version(user, timestamp, wait_to_save)
        template = '{timestamp} {actor} unlocked {target} for editing'
        log_event(user, 'unlock', target=self, timestamp=new.added,
                  template=template)
        self = new
        return new

    @transaction.atomic
    def lock(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        self.locked = timestamp
        self.locked_by = user
        # save obj now, don't wait for some other method after this
        template = '{timestamp} {actor} locked {target} for editing, making it read only'
        log_event(user, 'lock', target=self, timestamp=timestamp,
                  template=template)
        if not wait_to_save:
            self.save()

    @transaction.atomic
    def publish(self, user, timestamp=None):
        if self.valid:
            timestamp = timestamp if timestamp else tznow()
            if not self.locked:
                self.lock(user, timestamp, True)
            self.generated_html = self.generate_html()
            self.published = timestamp
            self.published_by = user
            self.save()
            template = '{timestamp} {actor} published {target}'
            log_event(user, 'publish', target=self, timestamp=timestamp,
                      template=template)

    @transaction.atomic
    def initialize_starting_answersets(self):
        for section in self.template.sections.filter(super_section__isnull=True):
            if not section.answersets.filter(plan=self).exists():
                self.ensure_answersets(section)

    @transaction.atomic
    def add_missing_answersets(self):
        for section in self.template.sections.filter(super_section__isnull=True):
            self.ensure_answersets(section)

    @transaction.atomic
    def create_answerset(self, section, parent=None):
        "Create another answerset for a specific section"
        a = AnswerSet(plan=self, section=section, parent=parent, valid=False)
        a.save()
        a.add_children()  # recursive
        return a

    @transaction.atomic
    def ensure_answersets(self, section, parent=None):
        "Ensure a section has the answersets it needs"
        created = False
        try:
            answerset, created = AnswerSet.objects.get_or_create(
                plan=self,
                section=section,
                parent=parent,
                defaults={'valid': False},
            )
        except AnswerSet.MultipleObjectsReturned:
            answerset = AnswerSet.objects.filter(
                plan=self,
                section=section,
                parent=parent
            ).last()
        if created and section.optional:
            answerset.skipped = True
            answerset.save()
        answerset.add_children()  # recursive
        return answerset

    # Traversal

    def get_first_question(self):
        return self.template.first_question

    def get_answersets_for_section(self, section, parent=NotSet):
        kwargs={'section': section, 'plan': self}
        if parent != NotSet:
            kwargs['parent'] = parent
        answersets = self.answersets.filter(**kwargs)
        if not answersets.exists():
            answerset = AnswerSet.objects.create(valid=False, **kwargs)
            answerset.add_children()
        answersets = self.answersets.filter(**kwargs)
        return answersets

    def get_linear_serialized_answersets(self, qs=None):
        if not qs:
            qs = self.answersets.all()
        return qs.lookup_map(qs)

    # Validation

    def clone_answersets(self, oldplan):
        answerset_mapping = {}
        for answerset in oldplan.answersets.all():
            new_answerset = answerset.clone(self)
            answerset_mapping[answerset] = new_answerset
        for old_answerset, new_answerset in answerset_mapping.items():
            if old_answerset.parent:
                new_answerset.parent = answerset_mapping[old_answerset.parent]
                new_answerset.save()

    def clean(self):
        if self.template_id:
            for section in self.template.sections.all():
                for answerset in self.answersets.filter(section=section):
                    if answerset.data or answerset.previous_data:
                        answerset.clean()

    def validate_data(self, recalculate: bool = True) -> bool:
        qids = self.question_ids_answered()
        wrong_pks = [str(pk) for pk in self.template.list_unknown_questions(qids)]
        if wrong_pks:
            error = 'The plan {} contains nonsense data: template has no questions for: {}'
            selfstr = '{} ({}), template {} ({})'.format(self, self.pk, self.template, self.pk)
            LOG.info(error.format(selfstr, ' '.join(wrong_pks)))
            self.clean()
        if self.is_empty:
            error = 'The plan {} ({}) has no data: invalid'
            LOG.info(error.format(self, self.pk))
            return False
        if recalculate:
            for answerset in self.answersets.all():
                answerset.validate()
        # All answersets of all sections must be valid for a plan to be valid
        for section in self.template.sections.all():
            if self.answersets.filter(section=section, valid=False, skipped=None).exists():
                return False
        return True

    def validate(self, user: User, recalculate: bool = False, commit: bool = True, timestamp: datetime = None) -> None:
        timestamp = timestamp if timestamp else tznow()
        valid = self.validate_data(recalculate)
        self.valid = valid
        self.last_validated = timestamp
        if commit:
            validity = {True: 'valid', False: 'invalid'}
            template = '{timestamp} {actor} validated {target}: {extra[validity]}'
            log_event(user, 'validate', target=self, timestamp=timestamp,
                      extra={'validity': validity[valid]}, template=template)
            self.save()

    # Summary/generated text

    def generate_html(self):
        context = self.get_context_for_generated_text()
        return render_to_string(GENERATED_HTML_TEMPLATE, context)

    def make_summary_of_answerset(self, answerset):
        sectionobj = self.linear_sections[answerset.section_id]
        decorate_answerset = sectionobj.section.get_data_summary
        data_summary = decorate_answerset(answerset.data)
        return SimpleNamespace(pk=answerset.pk, name=answerset.identifier,
                    valid=answerset.valid, data=data_summary)

    def get_summary_for_section(self, sectionobj, answersetobjs):
        num_answersets = sectionobj.num_answersets
        section = sectionobj.section
        num_valid_answersets = 0
        for answersetobj in answersetobjs:
            if answersetobj.answerset.valid:
                num_valid_answersets += 1
        is_valid = num_valid_answersets == num_answersets
        deletable_if_optional = section.optional and num_answersets
        deletable_if_repeatable = section.repeatable and num_answersets > 1
        addable_if_optional = section.optional and not num_answersets
        addable_if_repeatable = section.repeatable
        meta_summary = sectionobj.summary
        meta_summary['num_answersets'] = num_answersets
        meta_summary['valid'] = is_valid
        meta_summary['addable'] = bool(addable_if_repeatable or addable_if_optional)
        meta_summary['deletable'] = bool(deletable_if_optional or deletable_if_repeatable)
        meta_summary['answerset_parent_id'] = answersetobjs[0].parent_id

        answer_blocks = []
        for answersetobj in answersetobjs:
            decoration = answersetobj.decoration
            decoration.section = answersetobj.section
            parent_id = answersetobj.answerset.id
            if sectionobj.children and answersetobj.children:
                decoration.children = list()
                for subsection_id in sectionobj.children:
                    key = AnswerSetParentKey(self.id, subsection_id, parent_id)
                    asids = self.parent_map.get(key, tuple())
                    subsectionobj = self.linear_sections[subsection_id]
                    child_answersetobjs = [self.linear_answersets[asid] for asid in asids]
                    subsummary = self.get_summary_for_section(subsectionobj, child_answersetobjs)
                    decoration.children.append(subsummary)
            answer_blocks.append(decoration)
        return {
            'answersets': answer_blocks,
            'section': meta_summary,
        }

    def get_nested_summary(self):
        """Generate a summary of all question/answer pairs in all sections

        This assumes that each question may be answered more than once,
        basically: sections may be answered more than once.

        Optimized for making few calls to the database, by avoiding queries
        in loops.
        """
        sections = (self.template.sections
            .prefetch_related('super_section')
            .annotate(num_answersets=Count('answersets'))
            .order_by('position')
            .decorate(summary=get_section_meta_summary)
        )
        self.linear_sections = sections.lookup_map('num_answersets', 'summary', qs=sections)
        answersets = self.answersets.decorate(
            self.make_summary_of_answerset,
            qs=self.answersets.select_related('parent', 'section').order_by('pk')
        )
        self.parent_map = answersets.map_by_parent_key()
        self.linear_answersets = self.answersets.lookup_map(qs=answersets)
        summary = []
        # Avoid queries in loops
        for section in sections:
            if section.super_section:
                continue
            key = AnswerSetParentKey(self.id, section.id, None)
            asids = self.parent_map.get(key, tuple())
            answersets = []
            if asids:
                answersets = [self.linear_answersets[asid] for asid in asids]
            sectionobj = self.linear_sections[section.id]
            summary.append(self.get_summary_for_section(sectionobj, answersets))
        return summary

    def make_canned_text_of_answerset(self, answerset):
        section = answerset.section
        decorate_answerset = section.generate_canned_text
        data_summary = decorate_answerset(answerset.data)
        return SimpleNamespace(answerset=data_summary)

    def get_canned_text_for_section(self, sectionobj, answersetobjs):
        section = sectionobj.section
        meta_summary = {
            'depth': section.section_depth,
            'title': section.title,
            'introductory_text': mark_safe(section.introductory_text),
            'comment': mark_safe(section.comment),
            'num_answersets': sectionobj.num_answersets,
        }
        answer_blocks = []
        for answersetobj in answersetobjs:
            decoration = answersetobj.decoration
            parent_id = answersetobj.answerset.id
            if sectionobj.children and answersetobj.children:
                decoration.children = list()
                decoration.name = answersetobj.answerset.identifier
                for subsection_id in sectionobj.children:
                    key = AnswerSetParentKey(self.id, subsection_id, parent_id)
                    asids = self.parent_map.get(key, tuple())
                    subsectionobj = self.linear_sections[subsection_id]
                    child_answersetobjs = [self.linear_answersets[asid] for asid in asids]
                    subtext = self.get_canned_text_for_section(subsectionobj, child_answersetobjs)
                    decoration.children.append(subtext)
            answer_blocks.append(decoration)
        return {
            'answersets': answer_blocks,
            'section': meta_summary,
        }

    def get_nested_canned_text(self):
        texts = []
        self.parent_map = self.answersets.map_by_parent_key()
        answersets = self.answersets.decorate(
            self.make_canned_text_of_answerset,
            qs=self.answersets.select_related('parent', 'section').order_by('pk')
        )
        self.linear_answersets = self.answersets.lookup_map(qs=answersets)
        self.linear_sections = self.template.sections.lookup_map('num_answersets', 'summary')
        for section in self.template.sections.all():
            if section.super_section:
                continue
            key = AnswerSetParentKey(self.id, section.id, None)
            asids = self.parent_map.get(key, tuple())
            answersets = []
            if asids:
                answersets = [self.linear_answersets[asid] for asid in asids]
            sectionobj = self.linear_sections[section.id]
            texts.append(self.get_canned_text_for_section(sectionobj, answersets))
        return texts

    def get_context_for_generated_text(self):
        return {
            'data': self.total_answers,
            'plan': self,
            'template': self.template,
        }


class PlanImportMetadata(ClonableModel):
    DEFAULT_VIA = 'CLI'

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE,
                             related_name='import_metadata')
    origin = models.CharField(
        max_length=255,
        help_text='Where the plan was imported from',
    )
    original_template_pk = models.IntegerField(
        help_text='Copy of the original plan\'s template\'s primary key',
    )
    original_plan_pk = models.IntegerField(
        help_text='Copy of the original plan\'s primary key',
    )
    originally_cloned_from = models.IntegerField(
        blank=True,
        null=True,
        help_text='Copy of the original plan\'s "cloned_from"',
    )
    originally_locked = models.DateTimeField(
        blank=True, null=True,
        help_text='Copy of the original plan\'s "locked"'
    )
    originally_published = models.DateTimeField(
        blank=True, null=True,
        help_text='Copy of the original plan\'s "published"'
    )
    variant = models.CharField(max_length=32, default='single version')

    # metadata for the metadata
    imported = models.DateTimeField(default=tznow)
    # URL or method
    imported_via = models.CharField(max_length=255, default=DEFAULT_VIA)

    class Meta:
        verbose_name_plural = 'plan import metadata'
        indexes = [
            models.Index(fields=['original_plan_pk'],
                         name='pim_lookup_original_idx')
        ]

    def __str__(self):
        return f'Plan #{self.original_plan_pk} @ {self.origin}'

    def natural_key(self):
        return (self.origin, self.original_plan_pk)

    @transaction.atomic
    def clone(self, plan):
        "Make a complete copy of the import metadata and put it on <plan>"
        new = self.get_copy()
        return new


class PlanAccess(ClonableModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE,
                             related_name='plan_accesses')
    plan = models.ForeignKey(Plan, models.CASCADE, related_name='accesses')

    may_edit = models.BooleanField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'plan')

    def __repr__(self):
        return 'user: {}, plan:{}, may edit: {}'.format(
            self.user_id, self.plan_id, self.may_edit)

    def clone(self, plan):
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'plan', 'user'])
        self_dict['user'] = self.user
        new = self.__class__.objects.create(plan=plan, **self_dict)
        return new

    @property
    def access(self):
        return 'view and edit' if self.may_edit else 'view'
