from unittest import mock

from django.http.response import Http404
from django import test
from django.urls import reverse
from django.utils.timezone import now as utcnow

from easydmp.dmpt.models import Template, Section, BooleanQuestion, CannedAnswer
from easydmp.auth.models import User

from easydmp.plan import views
from easydmp.plan.models import Plan
from easydmp.plan.views import AbstractGeneratedPlanView


URLS = {
    'choose_template': {'public': False, 'kwargs': ()},
#     'plan_list': {'public': False, 'kwargs': ()},
#     'update_planaccess': {'public': False, 'kwargs': ('access',)},
#     'leave_plan': {'public': False, 'kwargs': ('access',)},
    'first_question': {'public': False, 'kwargs': ('plan',)},
    'lock_plan': {'public': False, 'kwargs': ('plan',)},
    'new_comment': {'public': False, 'kwargs': ('plan', 'question',)},
    'new_question': {'public': False, 'kwargs': ('plan', 'question',)},
    'plan_delete': {'public': False, 'kwargs': ('plan',)},
    'plan_detail': {'public': False, 'kwargs': ('plan',)},
    'plan_saveas': {'public': False, 'kwargs': ('plan',)},
    'publish_plan': {'public': False, 'kwargs': ('plan',)},
    'section_detail': {'public': False, 'kwargs': ('plan', 'section',)},
    'share_plan': {'public': False, 'kwargs': ('plan',)},
    'unlock_plan': {'public': False, 'kwargs': ('plan',)},
    'update_plan': {'public': False, 'kwargs': ('plan',)},
    'validate_plan': {'public': False, 'kwargs': ('plan',)},
}


def create_template(published=None):
    published = utcnow() if published else None
    t = Template.objects.create(title='test template', published=published)
    s = Section.objects.create(template=t, title='test section')
    q = BooleanQuestion.objects.create(section=s, obligatory=True)
    CannedAnswer.objects.create(question=q, choice='Yes')
    CannedAnswer.objects.create(question=q, choice='No')
    return t


def make_kwargs(args):
    kwargs = {}
    if 'plan' in args:
        kwargs['plan'] = Plan.objects.get().pk
    if 'question' in args:
        kwargs['question'] = BooleanQuestion.objects.get().pk
    if 'section' in args:
        kwargs['section'] = Section.objects.get().pk
    return kwargs


class AccessTestCase(test.TestCase):

    def setUp(self):
        self.template = create_template(True)
        self.user = User.objects.create(username='test user')
        self.user.set_password('password')
        self.plan = Plan.objects.create(
            template=self.template, title='test plan',
            added_by=self.user,
            modified_by=self.user,
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


class GeneratedViewTestCase(test.TestCase):

    def setUp(self):
        self.urlname = 'generated_plan_html'
        self.template = create_template(True)
        self.user = User.objects.create(username='test user')
        self.user.set_password('password')
        self.settings(STATIC_URL='/static/')

    def test_anon_access_generated_public(self):
        plan = Plan.objects.create(
            template=self.template, title='test plan',
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
        plan = Plan.objects.create(
            template=self.template, title='test plan',
            added_by=self.user,
            modified_by=self.user,
        )

        c = test.Client()
        kwargs = {'plan': plan.pk}
        response = c.get(reverse(self.urlname, kwargs=kwargs))
        self.assertEqual(response.status_code, 404, '{} should be hidden'.format(self.urlname))
