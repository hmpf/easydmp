# Generated by Django 2.2.18 on 2021-03-04 07:46

from django.db import migrations, models



def copy_published_to_locked(apps, schema_editor):
    Template = apps.get_model('dmpt', 'Template')
    Template.objects.exclude(published=None).update(locked=models.F('published'))


def copy_locked_to_published(apps, schema_editor):
    Template = apps.get_model('dmpt', 'Template')
    Template.objects.exclude(locked=None).update(published=models.F('locked'))


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0003_TemplateImportMetadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='locked',
            field=models.DateTimeField(blank=True, help_text='Date when the template was set read-only.', null=True),
        ),
        migrations.AlterField(
            model_name='template',
            name='published',
            field=models.DateTimeField(blank=True, help_text='Date when the template was made publically available.', null=True),
        ),
        migrations.RunPython(copy_published_to_locked, copy_locked_to_published),
        migrations.AddField(
            model_name='templateimportmetadata',
            name='originally_published',
            field=models.DateTimeField(blank=True, help_text='Copy of the original template\'s "published"', null=True),
        ),
    ]