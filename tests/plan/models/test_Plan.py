from collections import OrderedDict
import logging

from django import test
from django.test import tag, skipUnlessDBFeature

from easydmp.auth.models import User
from easydmp.dmpt.models import Template
from easydmp.plan.models import Plan
from tests.dmpt.factories import TemplateFactory, SectionFactory
from tests.plan.factories import PlanFactory


@tag('JSONField')
class TestPlanValidation(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)

    def test_validate_plan_empty_plan(self):
        plan = PlanFactory(template=self.template)
        plan.data = None
        plan.template.list_unknown_questions = lambda x: set()
        with self.assertLogs('easydmp.plan.models', level='INFO') as cm:
            result = plan.validate_data(recalculate=False)
            self.assertEqual(len(cm.output), 1)
            self.assertIn('has no data: invalid', cm.output[0])
            expected = False
            self.assertEqual(result, expected)

# TODO: replace with test that verifies that answers for deleted questions get
# deleted on save/verify
#     def test_validate_plan_wrong_pks_in_plan(self):
#         plan = PlanFactory(template=self.template)
#         plan.data = None
#         plan.template.list_unknown_questions = lambda x: set((56, 57))
#         with self.assertLogs(logger='easydmp.dmpt.models', level='ERROR') as log:
#             result = plan.validate_data(recalculate=False)
#             expected = False
#             self.assertEqual(result, expected)
#             self.assertIn('contains nonsense data:', log.output[0])
