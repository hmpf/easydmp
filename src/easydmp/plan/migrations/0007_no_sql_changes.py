# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-12 13:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0006_plan_visited_sections'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='visited_sections',
            field=models.ManyToManyField(blank=True, related_name='_plan_visited_sections_+', to='dmpt.Section'),
        ),
    ]
