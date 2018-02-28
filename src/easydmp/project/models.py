from django.db import models


class Project(models.Model):
    title = models.CharField(
        max_length=255,
        help_text='The name of the project a plan is for',
        blank=True,
        default='',
    )
    url = models.URLField(
        help_text='URL pointing to more information about the project, e.g., a home page',
        blank=True,
        default='',
    )
