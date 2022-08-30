from django import test
from django.db import IntegrityError

from easydmp.dmpt.models import ShortFreetextQuestion
from easydmp.dmpt.models import BooleanQuestion
from easydmp.dmpt.models import PositiveIntegerQuestion
from easydmp.plan.models import Plan, AnswerSet, Answer
from tests.dmpt.factories import TemplateFactory, SectionFactory


class TestAnswersetSkipped(test.TestCase):

    def test_skipped_may_never_be_false(self):
        template = TemplateFactory()
        section = SectionFactory.build(template=template)
        section.save()
        plan = Plan(template=template, added_by_id=1, modified_by_id=1, valid=False)
        plan.save()
        as1 = AnswerSet(plan=plan, section=section, skipped=False)
        with self.assertRaises(IntegrityError):
            as1.save()


class TestAnswerSetAutoCreate(test.TestCase):

    def test_answerset_is_created_on_plan_save(self):
        template = TemplateFactory()
        section = SectionFactory.build(template=template)
        section.save()
        plan = Plan(template=template, added_by_id=1, modified_by_id=1, valid=False)
        plan.save()
        answersets = AnswerSet.objects.filter(plan=plan)
        self.assertEqual(answersets.count(), 1)
        self.assertEqual(answersets[0].section, section)


class TestAnswerSetValidation(test.TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.template = TemplateFactory()
        cls.section = SectionFactory.build(template=cls.template)
        cls.section.save()
        cls.q1 = ShortFreetextQuestion(section=cls.section, position=1)
        cls.q2 = BooleanQuestion(section=cls.section, position=2)
        cls.q3 = PositiveIntegerQuestion(section=cls.section, position=3)
        cls.q1.save()
        cls.q2.save()
        cls.q3.save()
        cls.plan = Plan(template=cls.template, added_by_id=1, modified_by_id=1, valid=False)
        cls.plan.save()

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
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q1).valid)
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q2).valid)
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q3).valid)
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
        self.assertFalse(Answer.objects.get(answerset=as1, question=self.q1).valid)
        self.assertFalse(Answer.objects.get(answerset=as1, question=self.q2).valid)
        self.assertFalse(Answer.objects.get(answerset=as1, question=self.q3).valid)
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
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q1).valid)
        self.assertFalse(Answer.objects.get(answerset=as1, question=self.q2).valid)
        self.assertFalse(Answer.objects.get(answerset=as1, question=self.q3).valid)
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
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q1.pk).valid)
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q2.pk).valid)
        self.assertTrue(Answer.objects.get(answerset=as1, question=self.q3.pk).valid)
        self.assertTrue(as1.valid)


class TestAnswersetGetIdentifier(test.TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.template = TemplateFactory()
        cls.section = SectionFactory(template=cls.template, repeatable=True)
        cls.plan = Plan(template=cls.template, added_by_id=1, modified_by_id=1, valid=False)
        cls.plan.save()

    def test_no_identifier_question_should_yield_serial_number(self):
        as0 = AnswerSet.objects.get(plan=self.plan, section=self.section)
        as1 = AnswerSet(plan=self.plan, section=self.section, data={})
        as1.save()
        as2 = AnswerSet(plan=self.plan, section=self.section, data={})
        as2.save()
        self.assertEqual(as0.identifier, '1')
        self.assertEqual(as1.identifier, '2')
        self.assertEqual(as2.identifier, '3')

    def test_identifier_question_should_use_answer_in_data(self):
        section = SectionFactory(template=self.template, repeatable=True)
        iq = ShortFreetextQuestion(section=section)
        iq.save()
        section.identifier_question = iq
        section.save()
        identifier = 'foo'
        as1 = AnswerSet(plan=self.plan, section=section, data={
            str(iq.pk): {'choice': identifier, 'notes': ''},
        })
        as1.save()
        self.assertEqual(as1.identifier, identifier)

    def test_identifier_question_should_fallback_to_serial_number(self):
        section = SectionFactory(template=self.template, repeatable=True)
        iq = ShortFreetextQuestion(section=section)
        iq.save()
        section.identifier_question = iq
        section.save()
        as1 = AnswerSet(plan=self.plan, section=section, data={})
        as1.save()
        self.assertEqual(as1.identifier, '1')
