# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-03-22 09:26
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0028_add_shortfreetext_question_type'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='templateaccess',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='templateaccess',
            name='template',
        ),
        migrations.RemoveField(
            model_name='templateaccess',
            name='user',
        ),
        migrations.DeleteModel(
            name='TemplateAccess',
        ),
    ]
