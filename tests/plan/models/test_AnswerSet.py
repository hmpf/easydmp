from django import test

from easydmp.dmpt.models import ShortFreetextQuestion, BooleanQuestion, PositiveIntegerQuestion
from easydmp.plan.models import Plan, AnswerSet, Answer
from tests.dmpt.factories import TemplateFactory, SectionFactory


class TestAnswerSet(test.TestCase):

    def test_validate_answerset_data(self):
        template = TemplateFactory()
        plan = Plan(template=template, added_by_id=1, modified_by_id=1, valid=False)
        plan.save()
        section = SectionFactory.build(template=template)
        section.save()
        q1 = ShortFreetextQuestion(section=section, position=1)
        q2 = BooleanQuestion(section=section, position=2)
        q3 = PositiveIntegerQuestion(section=section, position=3)
        q1.save()
        q2.save()
        q3.save()

        as1 = AnswerSet(plan=plan, section=section, valid=False, data={
            str(q1.id): {
                "choice": "foo",
                "notes": "n1"
            },
            str(q2.id): {
                "choice": "True",
                "notes": "n2"
            },
            str(q3.id): {
                "choice": 1,
                "notes": "n3"
            }
        })
        as1.save()
        a1_1 = Answer(answerset=as1, question=q1, plan=plan, valid=False)
        a1_2 = Answer(answerset=as1, question=q2, plan=plan, valid=False)
        a1_3 = Answer(answerset=as1, question=q3, plan=plan, valid=False)
        a1_1.save()
        a1_2.save()
        a1_3.save()

        as1.validate()
        self.assertTrue(a1_1.valid)
        self.assertTrue(a1_2.valid)
        self.assertFalse(a1_3.valid)
