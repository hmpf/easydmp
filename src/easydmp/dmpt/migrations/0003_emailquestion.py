# Generated by Django 3.2.3 on 2021-09-13 11:32
from django.db import migrations

import easydmp.dmpt.models.questions.mixins


def register_email_type(apps, _):
    QuestionType = apps.get_model('dmpt', 'QuestionType')
    QuestionType.objects.get_or_create(id='email')


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0002_add_QuestionType_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailQuestion',
            fields=[
            ],
            options={
                'managed': False,
                'proxy': True,
            },
            bases=(easydmp.dmpt.models.questions.mixins.PrimitiveTypeMixin, easydmp.dmpt.models.questions.mixins.SaveMixin, 'dmpt.question'),
        ),
        migrations.RunPython(register_email_type, migrations.RunPython.noop),
    ]
