# Generated by Django 3.2.3 on 2021-09-15 08:32
from django.db import migrations

import easydmp.dmpt.models.questions.mixins


def register_iri_type(apps, _):
    QuestionType = apps.get_model('dmpt', 'QuestionType')
    QuestionType.objects.get_or_create(id='iri')


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0003_emailquestion'),
    ]

    operations = [
        migrations.CreateModel(
            name='IRIQuestion',
            fields=[
            ],
            options={
                'managed': False,
                'proxy': True,
            },
            bases=(easydmp.dmpt.models.questions.mixins.PrimitiveTypeMixin, easydmp.dmpt.models.questions.mixins.SaveMixin, 'dmpt.question'),
        ),
        migrations.RunPython(register_iri_type, migrations.RunPython.noop),
    ]
