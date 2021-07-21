# Generated by Django 3.2.3 on 2021-07-21 13:07

import django.core.serializers.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0014_move_data_into_answersets'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answerset',
            name='data',
            field=models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
        migrations.AlterField(
            model_name='answerset',
            name='previous_data',
            field=models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]
