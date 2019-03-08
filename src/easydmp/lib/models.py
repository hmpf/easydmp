from django.db import models


class ModifiedTimestampModel(models.Model):
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
