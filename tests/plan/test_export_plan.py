from pprint import pprint

from django.test import TestCase, override_settings

from easydmp.plan.export_plan import serialize_plan_export
from easydmp.plan.models import AnswerHelper

from tests.dmpt.factories import TemplateFactory
from tests.dmpt.factories import SectionFactory
from tests.dmpt.factories import BooleanQuestionFactory
from tests.plan.factories import PlanFactory

VERSION = 'blbl'


@override_settings(VERSION=VERSION)
class ExportPlanTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        t = TemplateFactory()
        s = SectionFactory(template=t)
        q = BooleanQuestionFactory(section=s, position=1)
        cls.template = t

    def test_exported_plan_references_template(self):
        plan = PlanFactory(template=self.template)
        comment = 'A comment'
        serialized_object = serialize_plan_export(plan.pk, comment=comment)
        result = serialized_object.data
        self.assertEqual(result['comment'], comment)
        self.assertEqual(result['metadata']['version'], VERSION)
        self.assertEqual(result['metadata']['template_id'], self.template.id)
        self.assertEqual(result['metadata']['template_copy']['template']['id'], self.template.id)

    def test_export_empty_plan(self):
        plan = PlanFactory(template=self.template)
        serialized_object = serialize_plan_export(plan.pk)
        result = serialized_object.data
        self.assertIn('plan', result)
        self.assertIn('answersets', result)
        self.assertEqual(result['answersets'][0]['data'], {})

    def test_export_simple_plan(self):
        question = self.template.questions.get()
        plan = PlanFactory(template=self.template)
        answerset = plan.answersets.get()
        answer = AnswerHelper(question, answerset)
        choice = {
            'choice': 'Yes',
            'notes': 'foo',
        }
        answer.save_choice(choice, plan.added_by)
        serialized_object = serialize_plan_export(plan.pk)
        result = serialized_object.data
        self.assertIn('answersets', result)
        self.assertEqual(result['answersets'][0]['data'][str(question.id)], choice)
