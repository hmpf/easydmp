# Generated by Django 2.2.18 on 2021-02-26 12:13

import django.contrib.postgres.fields.jsonb
import django.core.serializers.json
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0008_answerset_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='answerset',
            name='previous_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]