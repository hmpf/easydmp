# Generated by Django 2.2.17 on 2020-11-13 13:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0009_modernize_NullBooleanField'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PlanComment',
        ),
    ]
