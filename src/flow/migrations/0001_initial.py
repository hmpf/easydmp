# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-21 06:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Edge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('condition', models.CharField(blank=True, max_length=64)),
            ],
        ),
        migrations.CreateModel(
            name='FSA',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=16)),
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
                ('slug', models.SlugField(max_length=16)),
                ('start', models.BooleanField(default=False)),
                ('depends', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='flow.Node')),
                ('fsa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='flow.FSA')),
            ],
            options={
                'ordering': ('fsa',),
            },
        ),
        migrations.AddField(
            model_name='edge',
            name='next_node',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prev_nodes', to='flow.Node'),
        ),
        migrations.AddField(
            model_name='edge',
            name='prev_node',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='next_nodes', to='flow.Node'),
        ),
        migrations.AlterUniqueTogether(
            name='node',
            unique_together=set([('fsa', 'slug')]),
        ),
        migrations.AlterUniqueTogether(
            name='edge',
            unique_together=set([('prev_node', 'next_node')]),
        ),
    ]