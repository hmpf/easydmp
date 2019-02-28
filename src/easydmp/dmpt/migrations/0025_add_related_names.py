# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-03-01 07:08
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0024_template_box_choice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templategroupobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions_group', to='dmpt.Template'),
        ),
        migrations.AlterField(
            model_name='templateuserobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissions_user', to='dmpt.Template'),
        ),
    ]
