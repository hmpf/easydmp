# Generated by Django 2.2.16 on 2020-10-16 13:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0011_section_optional'),
        ('plan', '0002_change_booleanquestion_answers'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='QuestionValidity',
            new_name='Answer',
        ),
        migrations.RenameModel(
            old_name='SectionValidity',
            new_name='AnswerSet',
        ),
    ]
