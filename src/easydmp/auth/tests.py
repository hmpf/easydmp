from django.test import TestCase

from easydmp.auth.models import User


class UserNameTest(TestCase):

    def test_format_user_name(self):
        self.assertEquals('User Name (user@name)',
                          str(User.objects.create_user(username='user@name', full_name='User Name')))
        self.assertEquals('another@name',
                          str(User.objects.create_user(username='another@name', full_name='')))
