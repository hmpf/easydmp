# Generated by Django 2.2.13 on 2020-12-17 14:18

import django.contrib.postgres.fields.jsonb
import django.core.serializers.json
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0007_auto_20201111_1411_squashed_0010_delete_plancomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='answerset',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]