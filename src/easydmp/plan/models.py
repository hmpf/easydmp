from django.conf import settings
from django.db import models

from jsonfield import JSONField

# With postgres 9.4+, use this instead
# from django.contrib.postgres.fields import JSONField


class Plan(models.Model):
    title = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=8, blank=True)
    version = models.PositiveIntegerField(default=1)
    template = models.ForeignKey('dmpt.Template', related_name='plans')
    data = JSONField(default={})
    previous_data = JSONField(default={})
    added = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='added_plans')
    modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='modified_plans')

    class Meta:
        # Only one plan per template and version
        unique_together = ('template', 'version', 'title')

    def __str__(self):
        return self.title
