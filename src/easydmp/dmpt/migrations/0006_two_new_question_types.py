# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-11-10 11:28
from __future__ import unicode_literals

from django.db import migrations, models
import easydmp.dmpt.models


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0005_section_comment'),
    ]

    operations = [
        migrations.CreateModel(
            name='PositiveIntegerQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.CreateModel(
            name='ReasonQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.AlterField(
            model_name='question',
            name='input_type',
            field=models.CharField(choices=[('bool', 'bool'), ('choice', 'choice'), ('daterange', 'daterange'), ('multichoiceonetext', 'multichoiceonetext'), ('reason', 'reason'), ('positiveinteger', 'positiveinteger'),], max_length=18),
        ),
    ]
