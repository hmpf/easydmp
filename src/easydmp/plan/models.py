from __future__ import annotations

import logging
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from typing import Any, Set, Dict, TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.timezone import now as tznow

from easydmp.dmpt.forms import make_form
from easydmp.dmpt.utils import DeletionMixin
from easydmp.eventlog.utils import log_event
from easydmp.lib import dump_obj_to_searchable_string
from easydmp.lib.models import ClonableModel

from .utils import purge_answer
from .utils import get_editors_for_plan

if TYPE_CHECKING:
    from easydmp.auth.models import User

LOG = logging.getLogger(__name__)
GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'


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


class AnswerSet(ClonableModel):
    """
    A user's set of answers to a Section
    """
    identifier = models.CharField(max_length=120, blank=True, default='1')
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='answersets')
    section = models.ForeignKey('dmpt.Section', models.CASCADE, related_name='answersets')
    parent = models.ForeignKey('self', models.CASCADE, related_name='answersets', null=True, blank=True)
    valid = models.BooleanField(default=False)
    last_validated = models.DateTimeField(auto_now=True)
    # The user's answers, represented as a Question PK keyed dict in JSON.
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder, blank=True)
    previous_data = models.JSONField(default=dict, encoder=DjangoJSONEncoder, blank=True)

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
        ]

    def __str__(self):
        return '"{}" #{}, section: {}, plan: {}, valid: {}'.format(
            self.identifier,
            self.pk,
            self.section_id,
            self.plan_id,
            self.valid)

    def save(self, *args, **kwargs):
        if not self.identifier:
            self.identifier = self.generate_next_identifier()
        super().save(*args, **kwargs)
        if not self.answers.exists():
            self.initialize_answers()

    def generate_next_identifier(self):
        count = self.__class__.objects.filter(plan=self.plan, section=self.section).count()
        return str(count + 1)

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

    def add_children(self):
        for section in self.section.subsections.all():
            answerset = AnswerSet(plan=self.plan, section=section, parent=self)
            answerset.save()
            answerset.add_children()  # Cannot put this in self.save(), would loop

    @property
    def is_empty(self):
        return bool(self.data)

    def get_answer(self, question_id):
        return self.data.get(str(question_id), {})

    @transaction.atomic
    def update_answer(self, question_id, choice):
        lookup_question_id = str(question_id)
        previous_choice = self.data.get(lookup_question_id, None)
        if previous_choice:
            self.previous_data[lookup_question_id] = previous_choice
        self.data[lookup_question_id] = choice
        self.answers.update_or_create(
            question_id=int(question_id),
            defaults={'valid': True}
        )
        self.save()

    def get_choice(self, question_id):
        return self.get_answer(question_id).get('choice', None)

    def get_answersets_for_section(self, section):
        return self.plan.get_answersets_for_section(section)

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
    def clone(self, plan):
        new = self.__class__.objects.create(
            plan=plan,
            section=self.section,
            valid=self.valid,
            last_validated=self.last_validated
        )
        new.set_cloned_from(self)
        new.save(update_fields=['cloned_from', 'cloned_when'])
        # clone answers
        answermapping = {}
        for answer in self.answers.all():
            new_answer = answer.clone(answerset=new)
            answermapping[str(answer.question.pk)] = str(new_answer.question.pk)
        # clone data
        if self.data:
            for key, value in self.data.items():
                new.data[answermapping[key]] = value
        # clone previous_data
        if self.previous_data:
            for key, value in self.previous_data.items():
                new.previous_data[answermapping[key]] = value
        new.save(update_fields=['data', 'previous_data'])
        return new

    def initialize_answers(self):
        if Answer.objects.filter(answerset=self).exists():
            return
        answers = []
        for question in self.section.questions.all():
            answers.append(Answer(question=question, answerset=self))
        Answer.objects.bulk_create(answers)

    def validate(self, timestamp: datetime = None) -> bool:
        """
        Validates the answers and persists the validity state on this as well as on related Answers.

        Returns validity.
        """
        self.last_validated = timestamp or tznow()
        valids, invalids, = self.section.find_validity_of_questions(self.data)
        self.set_validity_of_answers(valids, invalids)
        subsections = self.section.ordered_sections()[1:]
        if subsections:
            valid = True
            if AnswerSet.objects.filter(section__in=subsections, valid=False).exists():
                valid = False
        else:
            valid = self.section.validate_data(self.data, (valids, invalids))
        self.valid = valid
        self.save(update_fields=('valid', 'last_validated'))
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


class Answer(ClonableModel):
    """
    An Answer contains metadata about an answer, such as validity. The actual answer the user gave is aggregated in
    AnswerSet.
    """
    answerset = models.ForeignKey(AnswerSet, models.CASCADE, related_name='answers')
    question = models.ForeignKey('dmpt.Question', models.CASCADE, related_name='+')
    valid = models.BooleanField(default=False)
    last_validated = models.DateTimeField(auto_now=True)

    def clone(self, plan, answerset):
        new = self.__class__.objects.create(
             question=self.question,
             answerset=answerset,
             valid=self.valid,
             last_validated=self.last_validated,
        )
        new.set_cloned_from(self)
        new.save(update_fields=['cloned_from', 'cloned_when'])
        return new

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('answerset', 'question'),
                name='plan_answer_one_answer_per_question')
        ]


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

    def save(self, user=None, question=None, recalculate=False, clone=False, **kwargs):
        self.search_data = dump_obj_to_searchable_string(self.total_answers)
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
            a = self.create_answerset(section)

    @transaction.atomic
    def create_answerset(self, section, parent=None):
        "Create another answerset for a specific section"
        a = AnswerSet(plan=self, section=section, parent=parent, valid=False)
        a.save()
        a.add_children()  # recursive
        return a

    # Traversal

    def get_first_question(self):
        return self.template.first_question

    def get_answersets_for_section(self, section):
        answersets = self.answersets.filter(section=section)
        if not answersets.exists():
            AnswerSet.objects.create(plan=self, section=section, valid=False)
            answersets = self.answersets.filter(section=section)
        return answersets

    # Validation

    def clone_answersets(self, oldplan):
        for answerset in oldplan.answersets.all():
            answerset.clone(self)

    def validate_data(self, recalculate: bool = True) -> bool:
        qids = self.question_ids_answered()
        wrong_pks = [str(pk) for pk in self.template.list_unknown_questions(qids)]
        if wrong_pks:
            error = 'The plan {} contains nonsense data: template has no questions for: {}'
            selfstr = '{} ({}), template {} ({})'.format(self, self.pk, self.template, self.pk)
            LOG.error(error.format(selfstr, ' '.join(wrong_pks)))
            return False
        if self.is_empty:
            error = 'The plan {} ({}) has no data: invalid'
            LOG.error(error.format(self, self.pk))
            return False
        if recalculate:
            for answerset in self.answersets.all():
                answerset.validate()
        # All answersets of all sections must be valid for a plan to be valid
        for section in self.template.sections.all():
            if self.answersets.filter(section=section, valid=False).exists():
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

    def get_summary_for_section(self, sectionobj, default_tag_level):
        section = sectionobj.section
        answersets = self.answersets.filter(section=section)
        num_answersets = answersets.count()
        is_valid = answersets.filter(valid=True).count() == num_answersets
        meta_summary = section.get_meta_summary(
            valid=is_valid,
            num_answersets=num_answersets,
            title_tag=f'h{section.section_depth+default_tag_level}',
        )
        answer_blocks = []
        for answerset in answersets.order_by('pk'):
            data_summary = section.get_data_summary(answerset.data)
            answer_blocks.append({
                'pk': answerset.pk,
                'name': answerset.identifier,
                'valid': answerset.valid,
                'data': data_summary,
            })
        subsections = []
        for sectionobj in sectionobj.subsections:
            subsummary = self.get_summary_for_section(sectionobj, default_tag_level)
            subsections.append(subsummary)
        return {
            'answersets': answer_blocks,
            'section': meta_summary,
            'subsections': tuple(subsections),
        }

    def get_nested_summary(self):
        """Generate a summary of all question/answer pairs in all sections

        This assumes that each question may be answered more than once,
        basically: sections may be answered more than once.
        """
        default_tag_level = 2
        summary = []
        for sectionobj in self.template.get_section_tree():
            summary.append(self.get_summary_for_section(sectionobj, default_tag_level))
        return summary

    def get_nested_canned_text(self):
        texts = []
        for section in self.template.ordered_sections():
            answersets = self.answersets.filter(section=section)
            num_answersets = answersets.count()
            meta_summary = section.get_meta_summary(num_answersets=num_answersets)
            answer_blocks = []
            for answerset in answersets.order_by('pk'):
                canned_text = section.generate_canned_text(answerset.data)
                answer_blocks.append({
                    'name': answerset.identifier,
                    'text': canned_text,
                })
            texts.append({
                'section': meta_summary,
                'answersets': answer_blocks,
            })
        return texts

    def get_context_for_generated_text(self):
        return {
            'data': self.total_answers,
            'output': self.get_nested_summary(),
            'text': self.get_nested_canned_text(),
            'plan': self,
            'template': self.template,
        }


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
