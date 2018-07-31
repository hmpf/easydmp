from copy import deepcopy
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.forms import model_to_dict
from django.template.loader import render_to_string
from django.utils.timezone import now as tznow

from jsonfield import JSONField

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

from flow.modelmixins import ClonableModel

from easydmp.dmpt.utils import DeletionMixin

from .utils import purge_answer
from .utils import get_editors_for_plan


GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'


class PlanQuerySet(models.QuerySet):

    def purge_answer(self, question_pk):
        qs = self.all()
        for plan in qs:
            purge_answer(plan, question_pk)

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

    def set_sections_as_valid(self, *sections):
        for section in sections:
            defaults = {'plan': self, 'valid': True, 'section': section}
            _ = SectionValidity.objects.update_or_create(
                plan=self,
                section=section,
                defaults=defaults
            )

    def set_sections_as_invalid(self, *sections):
        for section in sections:
            defaults = {'plan': self, 'valid': False, 'section': section}
            _ = SectionValidity.objects.update_or_create(
                plan=self,
                section=section,
                defaults=defaults
            )

    def set_questions_as_valid(self, *questions):
        for question in questions:
            defaults = {'plan': self, 'valid': True, 'question': question}
            _ = QuestionValidity.objects.update_or_create(
                plan=self,
                question=question,
                defaults=defaults
            )

    def set_questions_as_invalid(self, *questions):
        for question in questions:
            defaults = {'plan': self, 'valid': False, 'question': question}
            _ = QuestionValidity.objects.update_or_create(
                plan=self,
                question=question,
                defaults=defaults
            )

    def validate(self):
        valid = self.template.validate_plan(self)
        self.valid = valid
        self.last_validated = tznow()
        self.save()

    def copy_validations_from(self, oldplan):
        for sv in oldplan.section_validity.all():
            sv.clone(self)
        for qv in oldplan.question_validity.all():
            qv.clone(self)

    def copy_users_from(self, oldplan):
        for pa in oldplan.accesses.all():
            pa.clone(self)

    def save(self, question=None, **kwargs):
        super().save(**kwargs)
        if question is not None:
            # set visited
            self.visited_sections.add(question.section)
            topmost = question.section.get_topmost_section()
            if topmost:
                self.visited_sections.add(topmost)
            # set validated
            self.validate()
        self.set_adder_as_editor()

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
        return new

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
        self.modified_by =None
        self.modified = None
        self.published_by = None
        self.published = None

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
        return new

    def unlock(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        new = self.create_new_version(user, timestamp, wait_to_save)
        self = new
        return new

    def lock(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        self.locked = timestamp
        self.locked_by = user
        # save obj now, don't wait for some other method after this
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

    def publish(self, user, timestamp=None):
        if self.valid:
            timestamp = timestamp if timestamp else tznow()
            if not self.locked:
                self.lock(user, timestamp, True)
            self.generated_html = self.generate_html()
            self.published = timestamp
            self.published_by = user
            self.save()


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


class PlanComment(models.Model):
    plan = models.ForeignKey(Plan, related_name='comments')
    question = models.ForeignKey('dmpt.Question')
    comment = models.TextField()
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='plan_comments')
