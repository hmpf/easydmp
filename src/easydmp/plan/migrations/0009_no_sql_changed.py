# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-13 13:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0008_add_publishing_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='abbreviation',
            field=models.CharField(blank=True, help_text='An abbreviation of the plan title, if needed.', max_length=8),
        ),
        migrations.AlterField(
            model_name='plan',
            name='title',
            field=models.CharField(help_text='The title of the plan itself, used in the generated file', max_length=255),
        ),
    ]
