# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-09-27 11:07
from __future__ import unicode_literals

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.management import create_permissions
from django.db import migrations


# As usual, cannot use helper functions safely in the migrations


def move_to_guardian(apps, schema_editor):

    TemplateAccess = apps.get_model('dmpt', 'TemplateAccess')
    TemplateUserObjectPermission = apps.get_model('dmpt', 'TemplateUserObjectPermission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Template = apps.get_model('dmpt', 'Template')
    template_ct = ContentType.objects.get_for_model(Template)
    Permission = apps.get_model('auth', 'Permission')
    if not Permission.objects.exists():
        # Fresh database, no permissions exist yet so make them early
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, verbosity=0)
            app_config.models_module = None
    use_template = Permission.objects.get(codename='use_template', content_type=template_ct)
    for ta in TemplateAccess.objects.all():
        TemplateUserObjectPermission.objects.create(
            content_object=ta.template,
            user=ta.user,
            permission=use_template
        )
        ta.delete()


def move_to_templateaccess(apps, schema_editor):
    User = get_user_model()
    TemplateAccess = apps.get_model('dmpt', 'TemplateAccess')
    TemplateUserObjectPermission = apps.get_model('dmpt', 'TemplateUserObjectPermission')
    # The TemplateAccess system only supports 'use_template' == True, and only for users.
    # Disregard any other permissions as they won't be in use.
    for tuop in TemplateUserObjectPermission.objects.all():
        TemplateAccess.objects.create(user=tuop.user, template=tuop.content_object)
    TemplateUserObjectPermission.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dmpt', '0018_use_guardian_for_template'),
    ]

    operations = [
        migrations.RunPython(move_to_guardian, move_to_templateaccess),
    ]