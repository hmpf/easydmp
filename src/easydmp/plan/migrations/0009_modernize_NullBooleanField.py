# Generated by Django 3.1.3 on 2020-11-12 09:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0008_convert_to_jsonb'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plan',
            name='valid',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='planaccess',
            name='may_edit',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
