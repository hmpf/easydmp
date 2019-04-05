import logging
from copy import deepcopy
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db import transaction
from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.utils.timezone import now as tznow

from jsonfield import JSONField

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

from flow.modelmixins import ClonableModel

from easydmp.dmpt.forms import make_form
from easydmp.dmpt.utils import DeletionMixin
from easydmp.eventlog.utils import log_event

from .utils import purge_answer
from .utils import get_editors_for_plan


LOG = logging.getLogger(__name__)
GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'


class Answer():
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

    def get_question_validity(self):
        qv, _ = QuestionValidity.objects.get_or_create(
            plan=self.plan,
            question=self.question,
            defaults={'valid': False}
        )
        return qv

    def get_section_validity(self):
        sv, _ = SectionValidity.objects.get_or_create(
            plan=self.plan,
            section=self.section,
            defaults={'valid': False}
        )
        return sv

    def get_form(self, **form_kwargs):
        form = make_form(self.question, **form_kwargs)
        return form

    def save_choice(self, choice, saved_by):
        LOG.debug('q%s/p%s: Answer: previous %s current %s',
                  self.question_id, self.plan.pk, self.current_choice, choice)
        if self.current_choice != choice:
            LOG.debug('q%s/p%s: saving changes',
                      self.question_id, self.plan.pk)
            self.plan.modified_by = saved_by
            self.plan.previous_data[self.question_id] = self.current_choice
            self.plan.data[self.question_id] = choice
            self.plan.save(user=saved_by, question=self.question)
            LOG.debug('q%s/p%s: setting question valid',
                      self.question_id, self.plan.pk)
            self.question_validity.valid = True
            self.question_validity.save()
            if not self.section_validity.valid and self.section.validate_data(self.plan.data):
                LOG.debug('q%s/p%s: setting section valid',
                          self.question_id, self.plan.pk)
                self.section_validity.valid = True
                self.section_validity.save()

    def set_invalid(self):
        if self.question_validity.valid:
            LOG.debug('q%s/p%s: setting invalid', self.question_id, self.plan.pk)
            self.question_validity.valid = False
            self.question_validity.save()
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

    def editable(self, user):
        return self.filter(accesses__user=user, accesses__may_edit=True)

    def viewable(self, user):
        return self.filter(accesses__user=user)


class SectionValidity(ClonableModel):
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='section_validity')
    section = models.ForeignKey('dmpt.Section', models.CASCADE, related_name='+')
    valid = models.BooleanField()
    last_validated = models.DateTimeField(auto_now=True)

    def clone(self, plan):
        new = self.__class__(plan=plan, section=self.section, valid=self.valid,
                             last_validated=self.last_validated)
        new.set_cloned_from(self)
        new.save()
        return new

    class Meta:
        unique_together = ('plan', 'section')


class QuestionValidity(ClonableModel):
    plan = models.ForeignKey('plan.Plan', models.CASCADE, related_name='question_validity')
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
    template = models.ForeignKey('dmpt.Template', related_name='plans')
    valid = models.NullBooleanField()
    last_validated = models.DateTimeField(blank=True, null=True)
    data = JSONField(default={})
    previous_data = JSONField(default={})
    visited_sections = models.ManyToManyField('dmpt.Section', related_name='+', blank=True)
    generated_html = models.TextField(blank=True)
    doi = models.URLField(
        blank=True,
        default='',
        help_text='Use the URLified DOI, https://dx.doi.org/<doi>',
    )
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='added_plans')
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='modified_plans')
    locked = models.DateTimeField(blank=True, null=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  related_name='locked_plans', blank=True,
                                  null=True, on_delete=models.SET_NULL)
    published = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     related_name='published_plans',
                                     blank=True, null=True,
                                     on_delete=models.SET_NULL)

    objects = PlanQuerySet.as_manager()

    def __str__(self):
        return self.title

    def logprint(self):
        return 'Plan #{}: {}'.format(self.pk, self.title)

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

    def get_first_question(self):
        return self.template.first_question

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

    def create_section_validities(self):
        svs = []
        for section in self.template.sections.all():
            svs.append(SectionValidity(plan=self, section=section, valid=False))
        SectionValidity.objects.bulk_create(svs)

    def set_sections_as_valid(self, *section_pks):
        qs = SectionValidity.objects.filter(plan=self, section_id__in=section_pks)
        qs.update(valid=True)

    def set_sections_as_invalid(self, *section_pks):
        qs = SectionValidity.objects.filter(plan=self, section_id__in=section_pks)
        qs.update(valid=False)

    def create_question_validities(self):
        qvs = []
        sections = self.template.sections.all()
        for section in sections:
            for question in section.questions.all():
                qvs.append(QuestionValidity(plan=self, question=question, valid=False))
        QuestionValidity.objects.bulk_create(qvs)

    def set_questions_as_valid(self, *question_pks):
        qs = QuestionValidity.objects.filter(plan=self, question_id__in=question_pks)
        qs.update(valid=True)

    def set_questions_as_invalid(self, *question_pks):
        qs = QuestionValidity.objects.filter(plan=self, question_id__in=question_pks)
        qs.update(valid=False)

    def validate(self, user, recalculate=False, commit=True, timestamp=None):
        timestamp = timestamp if timestamp else tznow()
        valid = self.template.validate_plan(self, recalculate)
        self.valid = valid
        self.last_validated = timestamp
        if commit:
            validity = {True: 'valid', False: 'invalid'}
            template = '{timestamp} {actor} validated {target}: {extra[validity]}'
            log_event(user, 'validate', target=self, timestamp=timestamp,
                      extra={'validity': validity[valid]}, template=template)
            self.save()

    def copy_validations_from(self, oldplan):
        for sv in oldplan.section_validity.all():
            sv.clone(self)
        for qv in oldplan.question_validity.all():
            qv.clone(self)

    def copy_users_from(self, oldplan):
        for pa in oldplan.accesses.all():
            pa.clone(self)

    def save(self, user=None, question=None, recalculate=False, **kwargs):
        if user:
            self.modified_by = user
        if not self.pk: # New, empty plan
            super().save(**kwargs)
            self.create_section_validities()
            self.create_question_validities()
            self.set_adder_as_editor()
            LOG.info('Created plan "%s" (%i)', self, self.pk)
            template = '{timestamp} {actor} created {target}'
            log_event(self.added_by, 'create', target=self,
                      timestamp=self.added, template=template)
        else:
            template = '{timestamp} {actor} saved {target}'
            log_event(self.added_by, 'save', target=self,
                      timestamp=self.modified, template=template)
            if question is not None:
                # set visited
                self.visited_sections.add(question.section)
                topmost = question.section.get_topmost_section()
                if topmost:
                    self.visited_sections.add(topmost)
                # set validated
                self.validate(user, recalculate, commit=False)
            super().save(**kwargs)
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
        new.save()
        new.copy_validations_from(self)
        if keep_users:
            editors = set(self.get_editors())
            for editor in editors:
                new.add_user_to_editors(editor)
        template = '{timestamp} {actor} saved {action_object} as {target}'
        log_event(user, 'save as', target=new, action_object=self,
                  timestamp=new.added, template=template)
        return new

    @transaction.atomic
    def clone(self):
        new = deepcopy(self)
        new.pk = None
        new.id = None
        new.set_cloned_from(self)
        new.save()
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
        new.unset_status_metadata()
        new.added_by = user
        new.added = timestamp
        new.modified_by = user
        new.modified = timestamp
        new.version += self.version
        if not wait_to_save:
            new.save()
        template = '{timestamp} {actor} created {target}, a new version of {action_object}'
        log_event(user, 'create new version', target=new, action_object=self,
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

    def get_summary(self, data=None):
        if not data:
            data = self.data.copy()
        valid_sections = (SectionValidity.objects
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

    def generate_html(self):
        context = self.get_context_for_generated_text()
        return render_to_string(GENERATED_HTML_TEMPLATE, context)

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


class PlanAccess(ClonableModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name='plan_accesses')
    plan = models.ForeignKey(Plan, models.CASCADE, related_name='accesses')

    may_edit = models.NullBooleanField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'plan')

    def clone(self, plan):
        self_dict = model_to_dict(self, exclude=['id', 'pk', 'plan'])
        new = self.__class__.objects.create(plan=plan, **self_dict)
        return new

    @property
    def access(self):
        return 'view and edit' if self.may_edit else 'view'


class PlanComment(models.Model):
    plan = models.ForeignKey(Plan, related_name='comments')
    question = models.ForeignKey('dmpt.Question')
    comment = models.TextField()
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='plan_comments')
