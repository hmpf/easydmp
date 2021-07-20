from django import test

from easydmp.dmpt.models import ShortFreetextQuestion, BooleanQuestion, PositiveIntegerQuestion
from easydmp.plan.models import Plan, AnswerSet, Answer
from tests.dmpt.factories import TemplateFactory, SectionFactory


class TestAnswerSetValidation(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.plan = Plan(template=self.template, added_by_id=1, modified_by_id=1, valid=False)
        self.plan.save()
        self.section = SectionFactory.build(template=self.template)
        self.section.save()
        self.q1 = ShortFreetextQuestion(section=self.section, position=1)
        self.q2 = BooleanQuestion(section=self.section, position=2)
        self.q3 = PositiveIntegerQuestion(section=self.section, position=3)
        self.q1.save()
        self.q2.save()
        self.q3.save()

    def test_validate_answerset_data_ok(self):
        as1 = AnswerSet(plan=self.plan, section=self.section, valid=False, data={
            str(self.q1.id): {
                "choice": "foo",
                "notes": "n1"
            },
            str(self.q2.id): {
                "choice": "Yes",
                "notes": "n2"
            },
            str(self.q3.id): {
                "choice": 1,
                "notes": "n3"
            }
        })
        as1.save()
        as1.initialize_answers()
        as1.validate()
        self.assertTrue(Answer.objects.get(question=self.q1).valid)
        self.assertTrue(Answer.objects.get(question=self.q2).valid)
        self.assertTrue(Answer.objects.get(question=self.q3).valid)
        self.assertTrue(as1.valid)

    def test_validate_answerset_data_fail(self):
        as1 = AnswerSet(plan=self.plan, section=self.section, valid=False, data={
            str(self.q1.id): {
                "choice": None,
                "notes": "n1"
            },
            str(self.q2.id): {
                "choice": None,
                "notes": "n2"
            },
            str(self.q3.id): {
                "choice": "bogus",
                "notes": "n3"
            }
        })
        as1.save()
        as1.initialize_answers()
        as1.validate()
        self.assertFalse(Answer.objects.get(question=self.q1).valid)
        self.assertFalse(Answer.objects.get(question=self.q2).valid)
        self.assertFalse(Answer.objects.get(question=self.q3).valid)
        self.assertFalse(as1.valid)

    def test_validate_answerset_data_subset(self):
        as1 = AnswerSet(plan=self.plan, section=self.section, valid=False, data={
            str(self.q1.id): {
                "choice": "foo",
                "notes": "n1"
            }
        })
        as1.save()
        as1.initialize_answers()
        as1.validate()
        self.assertTrue(Answer.objects.get(question=self.q1).valid)
        self.assertFalse(Answer.objects.get(question=self.q2).valid)
        self.assertFalse(Answer.objects.get(question=self.q3).valid)
        self.assertFalse(as1.valid)

    def test_validate_answerset_bogus_answer(self):
        as1 = AnswerSet(plan=self.plan, section=self.section, valid=False, data={})
        as1.save()
        s_bogus = SectionFactory.build(template=self.template)
        s_bogus.save()
        q_bogus = BooleanQuestion(section=s_bogus, position=10)
        q_bogus.save()
        a_bogus = Answer(answerset=as1, question=q_bogus, valid=False)
        a_bogus.save()
        # No answer exists for q_bogus
        self.assertFalse(as1.validate())

    def test_validate_answerset(self):
        as1 = AnswerSet(plan=self.plan, section=self.section, valid=False, data={
            str(self.q1.id): {
                "choice": "foo",
                "notes": "n1"
            },
            str(self.q2.id): {
                "choice": "Yes",
                "notes": "n2"
            },
            str(self.q3.id): {
                "choice": 1,
                "notes": "n3"
            },
            "999": {
                "choice": "hmmm",
                "notes": "hmm"
            }
        })
        as1.save()
        as1.initialize_answers()
        as1.validate()  # Sets the answers valid
        self.assertTrue(Answer.objects.get(question=self.q1.pk).valid)
        self.assertTrue(Answer.objects.get(question=self.q2.pk).valid)
        self.assertTrue(Answer.objects.get(question=self.q3.pk).valid)
        self.assertTrue(as1.valid)
