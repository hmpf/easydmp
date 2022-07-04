"""
The heart of the link between RDA DCS and Questions is the ``path``, a pseudo
jg syntax.

The path

::
    ``.dmp.dataset[].description?``

points to the value "Crates with figurines from site 1" in the below
json-fragment::

    {
        "dmp": {
            "dataset": [
                {
                    "description": "Crates with figurines from site 1"
                }
            ]
        }
    }

The ``[]`` marks a repeatable key and the ``?`` an optional key. The actual jq
syntax to fetch the value is ``.dmp.dataset[0].description?``.
"""

from django.db import models
from django.utils.text import slugify


class RDADCSKey(models.Model):
    slug = models.SlugField(max_length=60, primary_key=True)
    path = models.CharField(
        max_length=60,
        unique=True,
        help_text='Path to value in jq path-syntax',
    )
    repeatable = models.BooleanField(blank=True, default=False)
    optional = models.BooleanField(blank=True, default=False)
    input_type = models.ForeignKey(
        'dmpt.questiontype',
        models.SET_NULL,
        blank=True,
        null=True,
        related_name='+'
    )

    def __str__(self):
        path, leaf = self.path.rsplit('.', 1)
        leaf, *_ = self.parse_key(leaf)
        if '.' in path:
            _, parent = path.rsplit('.', 1)
            parent, *_ = self.parse_key(parent)
            return f'{parent} {leaf}'
        else:
            return leaf

    def save(self, *args,**kwargs):
        self.slug = self.slugify_path(self.path)
        _, self.optional, self.repeatable = self.get_key(self.path)
        super().save(*args,**kwargs)

    @property
    def key(self):
        key, *_ = self.get_key(self.path)
        return key

    @classmethod
    def get_key(cls, path):
        _, key = path.rsplit('.', 1)
        return cls.parse_key(key)

    @classmethod
    def parse_key(cls, key):
        optional = False
        if key[-1] == '?':
            key = key[:-1]
            optional = True
        repeatable = False
        if key[-2:] == '[]':
            key = key[:-2]
            repeatable = True
        return key, optional, repeatable

    @staticmethod
    def slugify_path(path):
        path = ' '.join(path.split('.'))
        return slugify(f'1-{path}')


class RDADCSQuestionLinkQuerySet(models.QuerySet):

    def per_template(self, template):
        return self.filter(question__section__template=template)


class RDADCSQuestionLink(models.Model):
    key = models.ForeignKey(RDADCSKey, models.CASCADE)
    question = models.OneToOneField('dmpt.question', models.CASCADE)

    objects = RDADCSQuestionLinkQuerySet.as_manager()

    class Meta:
        unique_together = ('key', 'question')

    def __str__(self):
        return f'{self.key.path} -> {self.question_id}'


class RDADCSSectionLinkQuerySet(models.QuerySet):

    def per_template(self, template):
        return self.filter(section__template=template)


class RDADCSSectionLink(models.Model):
    key = models.ForeignKey(RDADCSKey, models.CASCADE)
    section = models.OneToOneField('dmpt.section', models.CASCADE)

    objects = RDADCSSectionLinkQuerySet.as_manager()

    class Meta:
        unique_together = ('key', 'section')

    def __str__(self):
        return f'{self.key.path} -> {self.section_id}'
