# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0020_obligatory_default_true'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='branching',
            field=models.NullBooleanField(),
        ),
    ]
