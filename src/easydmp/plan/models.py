from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils.timezone import now as tznow

from jsonfield import JSONField

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField

from .utils import purge_answer


class PlanQuerySet(models.QuerySet):

    def purge_answer(self, question_pk):
        qs = self.all()
        for plan in qs:
            purge_answer(plan, question_pk)


class Plan(models.Model):
    title = models.CharField(
        max_length=255,
        help_text='The title of the plan itself, used in the generated file'
    )
    abbreviation = models.CharField(
        max_length=8, blank=True,
        help_text='An abbreviation of the plan title, if needed.',
    )
    version = models.PositiveIntegerField(default=1)
    uuid = models.UUIDField(default=uuid4, editable=False)
    template = models.ForeignKey('dmpt.Template', related_name='plans')
    data = JSONField(default={})
    previous_data = JSONField(default={})
    visited_sections = models.ManyToManyField('dmpt.Section', related_name='+', blank=True)
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

    def save(self, question=None, **kwargs):
        super().save(**kwargs)
        if question is not None:
            self.visited_sections.add(question.section)
            topmost = question.section.get_topmost_section()
            if topmost:
                self.visited_sections.add(topmost)
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
        if keep_editors:
            editors = set(self.editor_group.user_set.all())
            for editor in editors:
                new.add_user_to_editor_group(editor)
        return new

    def create_new_version(self):
        self.id = None
        self.version += self.version
        super().save(force_insert=True)
        editors = self.editor_group.user_set.all()
        self.create_editor_group()
        for editor in editors:
            self.add_user_to_editor_group(editor)

    def lock(self, user, timestamp=None, wait_to_save=False):
        timestamp = timestamp if timestamp else tznow()
        self.locked = timestamp
        self.locked_by = user
        # save obj now, don't wait for some other method after this
        if not wait_to_save:
            self.save()

    def publish(self, user, timestamp=None):
        timestamp = timestamp if timestamp else tznow()
        if not self.locked:
            self.lock(user, timestamp, True)
        self.published = timestamp
        self.published_by = user
        self.save()


class PlanComment(models.Model):
    plan = models.ForeignKey(Plan, related_name='comments')
    question = models.ForeignKey('dmpt.Question')
    comment = models.TextField()
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='plan_comments')
