# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-03-20 13:07
from __future__ import unicode_literals

from django.db import migrations, models
import easydmp.dmpt.models


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0027_section_modified'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShortFreetextQuestion',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=(easydmp.dmpt.models.NoCheckMixin, easydmp.dmpt.models.SimpleFramingTextMixin, 'dmpt.question'),
        ),
        migrations.AlterField(
            model_name='question',
            name='input_type',
            field=models.CharField(choices=[('bool', 'bool'), ('choice', 'choice'), ('daterange', 'daterange'), ('multichoiceonetext', 'multichoiceonetext'), ('reason', 'reason'), ('shortfreetext', 'shortfreetext'), ('positiveinteger', 'positiveinteger'), ('externalchoice', 'externalchoice'), ('extchoicenotlisted', 'extchoicenotlisted'), ('externalmultichoiceonetext', 'externalmultichoiceonetext'), ('extmultichoicenotlistedonetext', 'extmultichoicenotlistedonetext'), ('namedurl', 'namedurl'), ('multinamedurlonetext', 'multinamedurlonetext'), ('multidmptypedreasononetext', 'multidmptypedreasononetext')], max_length=32),
        ),
    ]