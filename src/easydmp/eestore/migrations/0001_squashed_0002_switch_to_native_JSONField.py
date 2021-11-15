# Generated by Django 3.2.3 on 2021-08-03 09:17

import django.core.serializers.json
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('dmpt', '0001_squashed_0011_section_optional_squashed_0008_switch_to_native_JSONField'),
    ]

    operations = [
        migrations.CreateModel(
            name='EEStoreType',
            fields=[
                ('name', models.CharField(max_length=64, primary_key=True, serialize=False)),
            ],
            options={
                'db_table': 'easydmp_eestore_type',
                'verbose_name': 'EEStore type',
            },
        ),
        migrations.CreateModel(
            name='EEStoreSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64)),
                ('eestore_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sources', to='eestore.eestoretype')),
            ],
            options={
                'db_table': 'easydmp_eestore_source',
                'verbose_name': 'EEStore source',
            },
        ),
        migrations.CreateModel(
            name='EEStoreMount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('eestore_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eestore.eestoretype')),
                ('question', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='eestore', to='dmpt.question')),
                ('sources', models.ManyToManyField(blank=True, help_text="Select a subset of the eestore types' sources here. Keep empty to select all types.", to='eestore.EEStoreSource')),
            ],
            options={
                'db_table': 'easydmp_eestore_mount',
                'verbose_name': 'EEStore mount',
            },
        ),
        migrations.CreateModel(
            name='EEStoreCache',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('eestore_pid', models.CharField(max_length=255, unique=True)),
                ('eestore_id', models.IntegerField()),
                ('name', models.CharField(max_length=255)),
                ('uri', models.URLField(blank=True)),
                ('pid', models.CharField(blank=True, max_length=255)),
                ('remote_id', models.CharField(max_length=255)),
                ('data', models.JSONField(default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('last_fetched', models.DateTimeField(blank=True, null=True)),
                ('eestore_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='eestore.eestoretype')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='eestore.eestoresource')),
            ],
            options={
                'db_table': 'easydmp_eestore_cache',
                'verbose_name': 'EEStore cache',
            },
        ),
    ]