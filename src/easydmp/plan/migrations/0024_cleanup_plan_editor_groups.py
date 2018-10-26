# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-09-28 09:04
from __future__ import unicode_literals

from django.core.management.color import no_style
from django.db import connection
from django.db import migrations


def remove_plan_editors(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__startswith='plan-editors-').delete()
    # There might be hundreds of these groups, reset the sequence
    sequence_sql = connection.ops.sequence_reset_sql(no_style(), [Group])
    with connection.cursor() as cursor:
        for sql in sequence_sql:
            cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0023_remove_plan_editor_group'),
    ]

    operations = [
        migrations.RunPython(remove_plan_editors, migrations.RunPython.noop)
    ]