from django import test

from tests.dmpt.factories import TemplateFactory, SectionFactory
from tests.plan.factories import PlanFactory


class TestTemplateMiscMethods(test.TestCase):

    def test_list_unknown_questions(self):
        template = TemplateFactory()
        section = SectionFactory(template=template, position=1)

        bad_ids = set((56, 565678587))
        data = dict(zip(bad_ids, bad_ids))
        result = template.list_unknown_questions(data)
        self.assertEqual(bad_ids, result)
