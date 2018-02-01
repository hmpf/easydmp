# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-01 12:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0005_make_fsa_slug_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='edge',
            name='cloned_from',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.Edge'),
        ),
        migrations.AddField(
            model_name='edge',
            name='cloned_when',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fsa',
            name='cloned_from',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.FSA'),
        ),
        migrations.AddField(
            model_name='fsa',
            name='cloned_when',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='node',
            name='cloned_from',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.Node'),
        ),
        migrations.AddField(
            model_name='node',
            name='cloned_when',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
