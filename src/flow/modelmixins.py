from django.utils.timezone import now as utcnow

from django.db import models


__all__ = ['ClonableModel']


class ClonableModel(models.Model):
    cloned_from = models.ForeignKey('self', blank=True, null=True,
                                    related_name='clones',
                                    on_delete=models.SET_NULL)
    cloned_when = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def set_cloned_from(self, obj):
        self.cloned_from = obj
        self.cloned_when = utcnow()
