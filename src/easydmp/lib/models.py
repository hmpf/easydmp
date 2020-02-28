from copy import copy

from django.utils.timezone import now as utcnow
from django.db import models


__all__ = [
    'ModifiedTimestampModel',
    'ClonableModel',
]


class ModifiedTimestampModel(models.Model):
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ClonableModel(models.Model):
    cloned_from = models.ForeignKey('self', on_delete=models.SET_NULL,
                                    blank=True, null=True,
                                    related_name='clones')
    cloned_when = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def get_copy(self):
        new = copy(self)
        new.id = None
        new.pk = None
        try:
            delattr(new, '_prefetched_objects_cache')
        except AttributeError:
            pass
        return new

    def set_cloned_from(self, obj):
        self.cloned_from = obj
        self.cloned_when = utcnow()
