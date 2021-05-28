from unittest import mock

from django import test
from django.test import tag, skipUnlessDBFeature
from django.urls import reverse
from django.utils.timezone import now as utcnow

from tests import has_sufficient_json_support
from tests.dmpt.factories import create_smallest_template
from tests.plan.factories import PlanFactory
from tests.auth.factories import UserFactory


@tag('JSONField')
@skipUnlessDBFeature(*has_sufficient_json_support)
class GeneratedViewTestCase(test.TestCase):

    def setUp(self):
        self.urlname = 'generated_plan_html'
        self.template = create_smallest_template(True)
        self.user = UserFactory()
        self.settings(STATIC_URL='/static/')

    def test_anon_access_generated_public(self):
        plan = PlanFactory(
            template=self.template,
            added_by=self.user,
            modified_by=self.user,
            published=utcnow(),
        )

        c = test.Client()
        kwargs = {'plan': plan.pk}
        with mock.patch('easydmp.plan.views.log_event', return_value=None):
            response = c.get(reverse(self.urlname, kwargs=kwargs))
        self.assertEqual(response.status_code, 200, '{} is not public'.format(self.urlname))

    def test_anon_access_generated_notpublic(self):
        plan = PlanFactory(
            template=self.template,
            added_by=self.user,
            modified_by=self.user,
        )

        c = test.Client()
        kwargs = {'plan': plan.pk}
        response = c.get(reverse(self.urlname, kwargs=kwargs))
        self.assertEqual(response.status_code, 404, '{} should be hidden'.format(self.urlname))
