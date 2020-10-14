from datetime import datetime

from django import test

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from easydmp.plan.utils import GenerateRDA10


class RdaTest(test.TestCase):

    def test_rda10_export(self):
        template = Template.objects.create(title='testtemplate')
        u1 = User.objects.create(username='testuser1', email='a@b.com')
        plan_uuid = 'cccaced2-a381-48a4-9806-70b9e329a83d'
        p1 = Plan.objects.create(title='testplan1', added_by=u1, modified_by=u1, template=template, uuid=plan_uuid)
        dmp = GenerateRDA10(p1).get_dmp()
        foo = {'created': '2020-10-14T07:14:56.867371',
               'modified': '2020-10-14T07:14:56.867543',
               'language': 'eng',
               'title': 'testplan1',
               'dmp_id': {'identifier': 'a3adf473-f2f1-4a3f-a20d-3c0469bb6b39',
                          'type': 'other'},
               'contact': {'mbox': 'testuser1',
                           'name': 'testuser1',
                           'contact_id': {'identifier': '2',
                                          'type': 'other'}},
               'dataset': [
                   {'personal_data': 'unknown',
                    'sensitive_data': 'unknown',
                    'title': 'testplan1',
                    'dataset_id': {'identifier': 'a3adf473-f2f1-4a3f-a20d-3c0469bb6b39',
                                   'type': 'other'}}],
               'ethical_issues_exist': 'unknown',
               'contributor': [
                   {'mbox': 'testuser1',
                    'name': 'testuser1',
                    'contributor_id': {'identifier': '2',
                                       'type': 'other'},
                    'role': ['Unknown']}]}
        self.assertEqual('eng', dmp['dmp']['language'])
        self.assertEqual('testplan1', dmp['dmp']['title'])
        self.assertEqual(plan_uuid, dmp['dmp']['dmp_id']['identifier'])
        self.assertEqual('testuser1', dmp['dmp']['contact']['mbox'])  # TODO is this correct Hanne?
        self.assertEqual('testuser1', dmp['dmp']['contact']['name'])
        self.assertEqual(1, len(dmp['dmp']['dataset']))
        self.assertEqual('unknown', dmp['dmp']['dataset'][0]['personal_data'])
        self.assertEqual('unknown', dmp['dmp']['dataset'][0]['sensitive_data'])
        self.assertEqual('unknown', dmp['dmp']['ethical_issues_exist'])
        self.assertEqual(1, len(dmp['dmp']['contributor']))
        self.assertEqual('testuser1', dmp['dmp']['contributor'][0]['mbox'])  # TODO Hanne intentional
        self.assertEqual('testuser1', dmp['dmp']['contributor'][0]['name'])
