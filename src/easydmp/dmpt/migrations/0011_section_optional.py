# Generated by Django 2.2.12 on 2020-09-22 11:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0010_rename_obligatory_to_on_trunk'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='optional',
            field=models.BooleanField(default=False, help_text='True if this section is optional. The template designer needs to provide a wording to an automatically generated yes/no question at the start of the section.'),
        ),
    ]
