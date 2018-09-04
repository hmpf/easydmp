from copy import deepcopy
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.template.loader import render_to_string
from django.utils.timezone import now as tznow

from jsonfield import JSONField

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

from flow.modelmixins import ClonableModel

from easydmp.dmpt.utils import DeletionMixin

from .utils import purge_answer


GENERATED_HTML_TEMPLATE = 'easydmp/plan/generated_plan.html'


class PlanQuerySet(models.QuerySet):

    def purge_answer(self, question_pk):
        qs = self.all()
        for plan in qs:
            purge_answer(plan, question_pk)


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
    editor_group = models.ForeignKey('auth.Group', related_name='+', blank=True, null=True)

    objects = PlanQuerySet.as_manager()

    def __str__(self):
        return self.title

    def get_first_question(self):
        return self.template.first_question

    def create_editor_group(self):
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='plan-editors-{}'.format(self.pk))
        self.editor_group = group
        self.save()

    def add_user_to_editor_group(self, user):
        user.groups.add(self.editor_group)

    def set_adder_as_editor(self):
        self.add_user_to_editor_group(self.added_by)

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

    def copy_editors_from(self, oldplan):
        if not self.editor_group:
            self.create_editor_group()
            editors = set(oldplan.editor_group.user_set.all())
            for editor in editors:
                self.add_user_to_editor_group(editor)

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
        if not self.editor_group:
            self.create_editor_group()
            self.set_adder_as_editor()

    def save_as(self, title, user, abbreviation='', keep_editors=True, **kwargs):
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
        if keep_editors:
            editors = set(self.editor_group.user_set.all())
            for editor in editors:
                new.add_user_to_editor_group(editor)
        return new

    def clone(self):
        new = deepcopy(self)
        new.pk = None
        new.id = None
        new.set_cloned_from(self)
        new.save()
        new.copy_validations_from(self)
        new.copy_editors_from(self)
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
        return self.template.get_summary(data)

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


class PlanComment(models.Model):
    plan = models.ForeignKey(Plan, related_name='comments')
    question = models.ForeignKey('dmpt.Question')
    comment = models.TextField()
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='plan_comments')
