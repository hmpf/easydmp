from django import test
from django.test import tag, skipUnlessDBFeature
from django.urls import reverse
from django.utils.timezone import now as tznow

from easydmp.dmpt.models import Section, Question
from easydmp.plan.models import Plan, AnswerSet

from tests.dmpt.factories import create_smallest_template
from tests.plan.factories import PlanFactory
from tests.auth.factories import UserFactory


URLS = {
    'choose_template': {'public': False, 'kwargs': ()},
#     'plan_list': {'public': False, 'kwargs': ()},
#     'update_planaccess': {'public': False, 'kwargs': ('access',)},
#     'leave_plan': {'public': False, 'kwargs': ('access',)},
    'first_question': {'public': False, 'kwargs': ('plan',)},
    'lock_plan': {'public': False, 'kwargs': ('plan',)},
    'answer_question': {'public': False, 'kwargs': ('plan', 'question', 'answerset')},
    'plan_delete': {'public': False, 'kwargs': ('plan',)},
    'plan_detail': {'public': True, 'kwargs': ('plan',)},
    'plan_saveas': {'public': False, 'kwargs': ('plan',)},
    'publish_plan': {'public': False, 'kwargs': ('plan',)},
    'answerset_detail': {'public': False, 'kwargs': ('plan', 'section','answerset')},
    'share_plan': {'public': False, 'kwargs': ('plan',)},
    'unlock_plan': {'public': False, 'kwargs': ('plan',)},
    'update_plan': {'public': False, 'kwargs': ('plan',)},
    'validate_plan': {'public': False, 'kwargs': ('plan',)},
}


def make_kwargs(args):
    kwargs = {}
    if 'plan' in args:
        kwargs['plan'] = Plan.objects.get().pk
    if 'question' in args:
        kwargs['question'] = Question.objects.get().pk
    if 'section' in args:
        kwargs['section'] = Section.objects.get().pk
    if 'answerset' in args:
        kwargs['answerset'] = AnswerSet.objects.get().pk
    return kwargs


@tag('JSONField')
class PlanAccessTestCase(test.TestCase):

    def setUp(self):
        self.template = create_smallest_template(True)
        self.user = UserFactory()
        self.plan = PlanFactory(
            template=self.template,
            added_by=self.user,
            modified_by=self.user,
            published=tznow(),
        )

    def test_anon_access(self):
        c = test.Client()
        for urlname, obj in URLS.items():
            kwargs = make_kwargs(obj.get('kwargs', ()))
            url = reverse(urlname, kwargs=kwargs)
            try:
                response = c.get(url)
            except TypeError:
                self.fail('TypeError for url {}'.format(url))
            if obj['public']:
                self.assertEqual(response.status_code, 200, '{} is not public'.format(urlname))
            else:
                self.assertEqual(response.status_code, 302, '{} did not redirect'.format(urlname))
                location = response['location']
                self.assertEqual(location.split('?')[0], '/login/', '{} did not redirect to login'.format(urlname))
