from datetime import timedelta

from django.test import TestCase
from django.utils.timezone import now as tznow

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from easydmp.utils.stats import stats


class StatsTestCase(TestCase):

    def setUp(self):
        # django-guardian, *sigh*
        AnonymousUser = User.objects.get()
        self.min_all_user = 1
        self.min_last_30days_user = 0
        last_30days = tznow() - timedelta(days=30)
        if AnonymousUser.date_joined >= last_30days:
            self.min_last_30days_user = 1

    def test_no_users_no_stats(self):
        result = stats()
        expected = {
            'users': {
                'all': self.min_all_user,
                'last_30days': self.min_last_30days_user,
            },
            'plans': {
                'all': 0,
                'last_30days':0,
            },
            'domains': {
                'all': 0,
                'last_30days':0,
            },
        }
        self.assertDictEqual(result, expected)

    def test_some_users_and_plans_some_stats(self):
        template = Template.objects.create(title='testtemplate')
        u1 = User.objects.create(username='testuser1', email='a@b.com')
        u2 = User.objects.create(username='testuser2', email='b@c.com')
        Plan.objects.create(title='testplan1', joined_by=u1, modified_by=u1,
                            template=template)
        Plan.objects.create(title='testplan2', joined_by=u2, modified_by=u2,
                            template=template)

        result = stats()
        expected = {
            'users': {
                'all': 2 + self.min_all_user,
                'last_30days': self.min_last_30days_user,
            },
            'plans': {
                'all': 2,
                'last_30days': 2,
            },
            'domains': {
                'all': 2,
                'last_30days':2,
            },
        }
        self.assertDictEqual(result, expected)
