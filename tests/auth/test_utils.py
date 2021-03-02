import unittest

from django import test
from django.test import tag

from easydmp.auth.utils import generate_default_permission_strings
from easydmp.auth.utils import set_user_object_permissions

from tests.dmpt.factories import TemplateFactory

from .factories import UserFactory, SuperuserFactory, PermissionFactory


@tag('unittest')
class TestGenerateDefaultPermissionStrings(unittest.TestCase):

    def test_generate_default_permission_strings(self):
        result = generate_default_permission_strings('dogecoin')
        expected = [
            'add_dogecoin',
            'change_dogecoin',
            'delete_dogecoin',
            'view_dogecoin',  # 'view' not in use before Django 2.1
        ]
        self.assertEqual(result, expected)


@tag('database')
class TestSetUserObjectPermissions(test.TestCase):

    def test_superuser_gets_no_permissions(self):
        superuser = SuperuserFactory()
        template = TemplateFactory()
        perms_before = template.permissions_user.filter(user=superuser).count()
        set_user_object_permissions(superuser, template)
        perms_after = template.permissions_user.filter(user=superuser).count()
        self.assertEqual(perms_before, perms_after)

    def test_user_gets_default_permissions(self):
        user = UserFactory()
        template = TemplateFactory()
        perms_before = template.permissions_user.filter(user=user).count()
        set_user_object_permissions(user, template)
        perms_after = template.permissions_user.filter(user=user).count()
        self.assertNotEqual(perms_before, perms_after)
        self.assertEqual(perms_after, 4)

    def test_user_gets_extra_permissions(self):
        user = UserFactory()
        template = TemplateFactory()
        extra_permission = PermissionFactory(codename='test_permission',
                                             for_model='dmpt.template')
        set_user_object_permissions(user, template, [extra_permission])
        result = template.permissions_user.filter(user=user).filter(permission=extra_permission).exists()
        self.assertTrue(result)
