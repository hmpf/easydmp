# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-28 08:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0004_auto_20170922_0911'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='comment',
            field=models.TextField(blank=True),
        ),
    ]
