# Generated by Django 2.2.17 on 2020-12-07 07:25

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0002_section_repeatable'),
    ]

    operations = [
        migrations.CreateModel(
            name='TemplateImportMetadata',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin', models.CharField(help_text='Where the template was imported from', max_length=255)),
                ('original_template_pk', models.IntegerField(help_text="Copy of the original template's primary key")),
                ('originally_cloned_from', models.IntegerField(blank=True, help_text='Copy of the original template\'s "cloned_from"', null=True)),
                ('mappings', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('imported', models.DateTimeField(default=django.utils.timezone.now)),
                ('imported_via', models.CharField(default='CLI', max_length=255)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='import_metadata', to='dmpt.Template')),
            ],
            options={
                'verbose_name_plural': 'template import metadata',
            },
        ),
        migrations.AddIndex(
            model_name='templateimportmetadata',
            index=models.Index(fields=['original_template_pk'], name='tim_lookup_original_idx'),
        ),
        migrations.AddConstraint(
            model_name='templateimportmetadata',
            constraint=models.UniqueConstraint(fields=('origin', 'original_template_pk'), name='tim_unique_template_per_origin_constraint'),
        ),
    ]