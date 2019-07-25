from django.test import TestCase

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from easydmp.utils.stats import stats


class StatsTestCase(TestCase):

    def test_no_users_no_stats(self):
        result = stats()
        expected = {
            'users': {
                'total': 0,
                'last_30days':0,
            },
            'plans': {
                'total': 0,
                'last_30days':0,
            },
        }
        self.assertDictEqual(result, expected)

    def test_some_users_and_plans_some_stats(self):
        template = Template.objects.create(title='testtemplate')
        u1 = User.objects.create(username='testuser1')
        u2 = User.objects.create(username='testuser2')
        Plan.objects.create(title='testplan1', added_by=u1, modified_by=u1,
                            template=template)
        Plan.objects.create(title='testplan2', added_by=u2, modified_by=u2,
                            template=template)

        result = stats()
        expected = {
            'users': {
                'total': 2,
                'last_30days': 2,
            },
            'plans': {
                'total': 2,
                'last_30days': 2,
            },
        }
        self.assertDictEqual(result, expected)
