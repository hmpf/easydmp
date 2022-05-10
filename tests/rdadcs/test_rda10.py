from datetime import datetime

from django import test
from django.test import tag, skipUnlessDBFeature

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from easydmp.rdadcs.lib.exporting import GenerateRDA10

from tests import has_sufficient_json_support

@tag('JSONField')
@skipUnlessDBFeature(*has_sufficient_json_support)
class RdaTest(test.TestCase):

    def test_rda10_export(self):
        template = Template.objects.create(title='testtemplate')
        u1 = User.objects.create(username='testuser1', full_name='Test 1. User', email='a@b.com')
        plan_uuid = 'cccaced2-a381-48a4-9806-70b9e329a83d'
        p1 = Plan.objects.create(title='testplan1', added_by=u1, modified_by=u1, template=template, uuid=plan_uuid)
        dmp = GenerateRDA10(p1).get_dmp()
        self.assertEqual('eng', dmp['dmp']['language'])
        self.assertEqual('testplan1', dmp['dmp']['title'])
        self.assertEqual(plan_uuid, dmp['dmp']['dmp_id']['identifier'])
        self.assertEqual('a@b.com', dmp['dmp']['contact']['mbox'])
        self.assertEqual('Test 1. User', dmp['dmp']['contact']['name'])
        self.assertEqual(1, len(dmp['dmp']['dataset']))
        self.assertEqual('unknown', dmp['dmp']['dataset'][0]['personal_data'])
        self.assertEqual('unknown', dmp['dmp']['dataset'][0]['sensitive_data'])
        self.assertEqual('unknown', dmp['dmp']['ethical_issues_exist'])
        self.assertEqual(1, len(dmp['dmp']['contributor']))
        self.assertEqual('a@b.com', dmp['dmp']['contributor'][0]['mbox'])
        self.assertEqual('Test 1. User', dmp['dmp']['contributor'][0]['name'])
