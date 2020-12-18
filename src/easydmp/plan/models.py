import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Set
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.utils.timezone import now as tznow

from easydmp.dmpt.forms import make_form
from easydmp.dmpt.utils import DeletionMixin
from easydmp.eventlog.utils import log_event
from easydmp.lib.models import ClonableModel

from .utils import purge_answer
from .utils import get_editors_for_plan


LOG = logging.getLogger(__name__)
GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'


class AnswerHelper():
    "Helper-class combining a Question and a Plan"

    def __init__(self, question, plan):
        self.question = question.get_instance()
        self.plan = plan
        # IMPORTANT: json casts ints to string as keys in dicts, so use strings
        self.question_id = str(self.question.pk)
        self.has_notes = self.question.has_notes
        self.section = self.question.section
        self.question_validity = self.get_question_validity()
        self.section_validity = self.get_section_validity()
        self.current_choice = plan.data.get(self.question_id, {})

    def get_initial(self, data):
        choice = data.get(self.question_id, {})
        return choice

    def get_question_validity(self):
        qv, _ = Answer.objects.get_or_create(
            plan=self.plan,
            question=self.question,
            defaults={'valid': False}
        )
        return qv

    def get_section_validity(self):
        sv, _ = AnswerSet.objects.get_or_create(
            plan=self.plan,
            section=self.section,
            defaults={'valid': False}
        )
        return sv

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
            self.plan.previous_data[self.question_id] = self.current_choice
            self.plan.data[self.question_id] = choice
            self.plan.save(user=saved_by, question=self.question)
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
        if not self.question_validity.valid:
            LOG.debug('set_valid: q%s/p%s',
                      self.question_id, self.plan.pk)
            self.question_validity.valid = True
            self.question_validity.save()
            if not self.section_validity.valid and self.section.validate_data(self.plan.data):
                LOG.debug('set_valid: q%s/p%s: section %',
                          self.question_id, self.plan.pk, self.section.pk)
                self.section_validity.valid = True
                self.section_validity.save()

    def set_invalid(self):
        if self.question_validity.valid:
            LOG.debug('set_invalid: q%s/p%s', self.question_id, self.plan.pk)
            self.question_validity.valid = False
            self.question_validity.save()
            LOG.debug('set_invalid: q%s/p%s: section %',
                      self.question_id, self.plan.pk, self.section.pk)
            self.section_validity.valid = False
            self.section_validity.save()


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


class AnswerSet(ClonableModel):
    """
    A user's set of answers to a Section
    """
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='answersets')
    section = models.ForeignKey('dmpt.Section', models.CASCADE, related_name='+')
    valid = models.BooleanField()
    last_validated = models.DateTimeField(auto_now=True)
    # The user's answers, represented as a Question PK keyed dict in JSON.
    data = JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        unique_together = ('plan', 'section')

    def __str__(self):
        return 'section: {}, plan: {}, valid: {}'.format(
            self.section_id,
            self.plan_id,
            self.valid)

    def clone(self, plan):
        new = self.__class__(plan=plan, section=self.section, valid=self.valid,
                             last_validated=self.last_validated)
        new.set_cloned_from(self)
        new.save()
        return new

    def validate(self, timestamp:datetime = None) -> bool:
        """
        Validates the answers and persists the validity state. Returns validity
        """
        valids, invalids = self.section.find_validity_of_questions(self.data)
        self.set_validity_of_answers(valids, invalids)
        self.last_validated = timestamp or tznow()
        self.valid = not invalids and len(valids) == len(self.data)
        self.save()
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
                raise ValueError('No question for answer {} in validation'.format(answer.pk))
            answer.save()


class Answer(ClonableModel):
    """
    An Answer contains metadata about an answer, such has validity. The actual answer the user gave is aggregated in
    AnswerSet.
    """
    # TODO: remove in sync with linking to correct answersets, updating unique_together
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='question_validity')
    # TODO: make non nullable later
    answerset = models.ForeignKey(AnswerSet, models.CASCADE, related_name='answers', null=True)
    question = models.ForeignKey('dmpt.Question', models.CASCADE, related_name='+')
    valid = models.BooleanField()
    last_validated = models.DateTimeField(auto_now=True)

    def clone(self, plan):
        new = self.__class__(plan=plan, question=self.question,
                             valid=self.valid,
                             last_validated=self.last_validated)
        new.set_cloned_from(self)
        new.save()
        return new

    class Meta:
        unique_together = ('plan', 'question')


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
    data = JSONField(default=dict, encoder=DjangoJSONEncoder)
    previous_data = JSONField(default=dict, encoder=DjangoJSONEncoder)
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

    def delete_answers(self, question_ids, commit=True):
        deleted = set()
        for question_id in question_ids:
            str_id = str(question_id)
            if str_id in self.data:
                self.previous_data[str_id] = self.data.pop(str_id)
                deleted.add(question_id)
        if commit:
            self.quiet_save()
        LOG.debug('delete_answers: %s', deleted)
        return deleted

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
        hidden = self.delete_answers(delete, commit=False)
        LOG.info('hide_unreachable_answers_after: Hide %s, show %s',
                 hidden or None, show or None)
        # Report whether a save is necessary
        return bool(hidden) or bool(show)

    def hide_unreachable_answers(self, section_qs=None):
        """Hide all unreachable answers of a plan or section"""
        if not self.data:
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
        answer_ids = set([int(key) for key in self.data.keys()])
        for section in all_sections.order_by('position'):
            questions = section.questions.filter(on_trunk=True).order_by('position')
            # Skip unanswered sections so they don't show up in the report
            if not (answer_ids & set(questions.values_list('id', flat=True))):
                continue
            LOG.debug('hide_unreachable_answers: Section "%s" (%s)', section,
                      section.id)
            # Go, go, go
            for question in questions:
                changed.add(self.hide_unreachable_answers_after(question))
        if any(changed):
            # One save per plan
            self.quiet_save()
        # Report if the plan was changed
        return any(changed)

    def _search_data_in(self, obj: Any) -> str:
        """
        A string of all text data in the JSON object, space separated
        """
        ret = ""
        if not obj:
            return ret
        if isinstance(obj, str):
            ret += "{} ".format(obj)
        if isinstance(obj, int):
            ret += "{} ".format(obj)
        if isinstance(obj, list):
            ret += " ".join([self._search_data_in(i) for i in obj])
        if isinstance(obj, dict):
            for k, v in obj.items():
                ret += self._search_data_in(k)
                ret += self._search_data_in(v)
        return ret

    def save(self, user=None, question=None, recalculate=False, clone=False, **kwargs):
        self.search_data = self._search_data_in(self.data)
        if user:
            self.modified_by = user
        if not self.pk: # New, empty plan
            super().save(**kwargs)
            if not clone:
                self.create_section_validities()
                self.create_question_validities()
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
            data=self.data,
            previous_data=self.previous_data,
            added_by=user,
            modified_by=user,
        )
        new.save(clone=True)
        new.copy_validations_from(self)
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
        new.copy_validations_from(self)
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

    # Template traversal

    def get_first_question(self):
        return self.template.first_question

    # Validation

    def create_section_validities(self):
        # TODO: To be changed to create_answersets
        svs = []
        for section in self.template.sections.all():
            svs.append(AnswerSet(plan=self, section=section, valid=False))
        AnswerSet.objects.bulk_create(svs)

    def create_question_validities(self):
        # TODO: Use method on AnswerSet instead
        qvs = []
        sections = self.template.sections.all()
        for section in sections:
            for question in section.questions.all():
                qvs.append(Answer(plan=self, question=question, valid=False))
        Answer.objects.bulk_create(qvs)

    def set_validity_of_sections(self, valids, invalids):
        # TODO: will work on answersets instead
        self._set_sections_as_valid(*valids)
        self._set_sections_as_invalid(*invalids)

    def _set_sections_as_valid(self, *section_pks):
        # TODO: will work on answersets instead
        qs = self.answersets.filter(section_id__in=section_pks)
        qs.update(valid=True)

    def _set_sections_as_invalid(self, *section_pks):
        # TODO: will work on answersets instead
        qs = self.answersets.filter(section_id__in=section_pks)
        qs.update(valid=False)

    def set_validity_of_questions(self, valids, invalids):
        self.set_questions_as_valid(*valids)
        self.set_questions_as_invalid(*invalids)

    def set_questions_as_valid(self, *question_pks):
        # TODO: Maybe turn into function?
        qs = Answer.objects.filter(plan=self, question_id__in=question_pks)
        qs.update(valid=True)

    def set_questions_as_invalid(self, *question_pks):
        # TODO: Maybe turn into function?
        qs = Answer.objects.filter(plan=self, question_id__in=question_pks)
        qs.update(valid=False)

    def copy_validations_from(self, oldplan):
        # TODO: Use answersets instead of section_validities
        for sv in oldplan.answersets.all():
            sv.clone(self)
        for qv in oldplan.question_validity.all():
            qv.clone(self)

    def validate_data(self, recalculate=True):
        wrong_pks = [str(pk) for pk in self.template.list_unknown_questions(self.data)]
        if wrong_pks:
            error = 'The self {} contains nonsense data: template has no questions for: {}'
            selfstr = '{} ({}), template {} ({})'.format(self, self.pk, self.template, self.pk)
            LOG.error(error.format(selfstr, ' '.join(wrong_pks)))
            return False
        if not self.data:
            error = 'The self {} ({}) has no data: invalid'
            LOG.error(error.format(self, self.pk))
            return False
        if recalculate:
            for sv in self.answersets.all():
                valids, invalids = sv.section.find_validity_of_questions(self.data)
                self.set_validity_of_questions(valids, invalids)
            valids, invalids = self.template.find_validity_of_sections(self.data)
            self.set_validity_of_sections(valids, invalids)
        if self.answersets.filter(valid=True).count() == self.template.sections.count():
            return True
        return False

    def validate(self, user, recalculate=False, commit=True, timestamp=None):
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

    def get_summary(self, data=None):
        if not data:
            data = self.data.copy()
        valid_sections = (AnswerSet.objects
                          .filter(valid=True, plan=self)
                          )
        valid_ids = valid_sections.values_list('section__pk', flat=True)
        summary = self.template.get_summary(data, valid_ids)
        return summary

    def get_canned_text(self, data=None):
        if not data:
            data = self.data.copy()
        return self.template.generate_canned_text(data)

    def get_context_for_generated_text(self):
        data = self.data.copy()
        return {
            'data': data,
            'output': self.get_summary(data),
            'text': self.get_canned_text(data),
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
