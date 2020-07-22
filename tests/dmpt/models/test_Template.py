from django import test

from tests.dmpt.factories import TemplateFactory, SectionFactory
from tests.plan.factories import PlanFactory


class TestTemplateMiscMethods(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)

    def test_list_unknown_questions(self):
        plan = PlanFactory(template=self.template)
        bad_ids = set((56, 565678587))
        plan.data = dict(zip(bad_ids, bad_ids))
        result = self.template.list_unknown_questions(plan)
        self.assertEqual(bad_ids, result)

    def test_validate_plan_empty_plan(self):
        plan = PlanFactory(template=self.template)
        plan.data = None
        self.template.list_unknown_questions = lambda x: set()
        result = self.template.validate_plan(plan, recalculate=False)
        expected = False
        self.assertEqual(result, expected)

    def test_validate_plan_wrong_pks_in_plan(self):
        plan = PlanFactory(template=self.template)
        plan.data = None
        self.template.list_unknown_questions = lambda x: set((56, 57))
        with self.assertLogs(logger='easydmp.dmpt.models', level='ERROR') as log:
            result = self.template.validate_plan(plan, recalculate=False)
            expected = False
            self.assertEqual(result, expected)
            self.assertIn('contains nonsense data:', log.output[0])
