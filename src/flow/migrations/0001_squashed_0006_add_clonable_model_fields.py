# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-08-01 10:57
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FSA',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.FSA')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('slug', models.SlugField(max_length=40, unique=True)),
            ],
            options={
                'verbose_name_plural': 'FSAs',
                'verbose_name': 'FSA',
            },
        ),
        migrations.CreateModel(
            name='Node',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.Node')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('slug', models.SlugField(max_length=40)),
                ('start', models.BooleanField(default=False)),
                ('depends', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='flow.Node')),
                ('fsa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='flow.FSA')),
                ('end', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('fsa',),
            },
        ),
        migrations.AlterUniqueTogether(
            name='node',
            unique_together=set([('fsa', 'slug')]),
        ),
        migrations.CreateModel(
            name='Edge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cloned_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='clones', to='flow.Edge')),
                ('cloned_when', models.DateTimeField(blank=True, null=True)),
                ('condition', models.CharField(blank=True, max_length=64)),
                ('next_node', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prev_nodes', to='flow.Node')),
                ('prev_node', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next_nodes', to='flow.Node')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='edge',
            unique_together=set([('condition', 'prev_node', 'next_node')]),
        ),
    ]