# Generated by Django 3.2.3 on 2021-11-02 13:44

from django.db import migrations, models

NOTELESS_FIELDS = ('shortfreetext', 'reason')


def set_allow_notes(apps, schema_editor):
    QuestionType = apps.get_model('dmpt', 'QuestionType')
    for qt in QuestionType.objects.filter(id__in=NOTELESS_FIELDS):
        qt.allow_notes = False
        qt.save()


def set_has_notes(apps, schema_editor):
    Question = apps.get_model('dmpt', 'Question')
    for q in Question.objects.filter(input_type_id__in=NOTELESS_FIELDS):
        q.has_notes = False
        q.save()
    for q in Question.objects.exclude(input_type_id__in=NOTELESS_FIELDS):
        q.has_notes = True
        q.save()


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0004_iriquestion'),
    ]

    operations = [
        migrations.AddField(
            model_name='questiontype',
            name='allow_notes',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(set_allow_notes, migrations.RunPython.noop),
        migrations.AddField(
            model_name='question',
            name='has_notes',
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(set_has_notes, migrations.RunPython.noop),
    ]
