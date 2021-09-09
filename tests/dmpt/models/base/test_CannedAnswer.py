from datetime import date

from django import test

from easydmp.dmpt.positioning import Move

from tests.dmpt.factories import (TemplateFactory, QuestionFactory,
                                  SectionFactory, BooleanQuestionFactory,
                                  ChoiceQuestionFactory, CannedAnswerFactory,
                                  ReasonQuestionFactory)


class TestGetCannedAnswerMethods(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)

    def test_extra_fields_get_canned_answer(self):
        q = BooleanQuestionFactory(section=self.section, create_canned_answers=False)
        expected = ''
        result = q.get_canned_answer(True, foo='foo', bar='bar')
        self.assertEqual(result, expected)

    def test_bool_no_text_get_canned_answer(self):
        q = BooleanQuestionFactory(section=self.section, create_canned_answers=False)
        result = q.get_canned_answer(True)
        self.assertEqual(result, '')

    def test_bool_one_text_get_canned_answer(self):
        q = BooleanQuestionFactory(section=self.section, create_canned_answers=False)
        expected = 'ABC 123'
        t_Yes = CannedAnswerFactory(question=q, canned_text=expected)
        result_TRUE = q.get_canned_answer('Yes')
        self.assertEqual(result_TRUE, expected)
        result_whatever = q.get_canned_answer('No')
        self.assertEqual(result_whatever, expected)

    def test_bool_get_canned_answer(self):
        q = BooleanQuestionFactory(section=self.section, create_canned_answers=False)
        t_Yes_expected = 'ABC 123'
        t_Yes = CannedAnswerFactory(question=q, choice='Yes', canned_text=t_Yes_expected)
        t_No_expected = 'DEF 456'
        t_No = CannedAnswerFactory(question=q, choice='No', canned_text=t_No_expected)
        self.assertEqual(set((t_Yes, t_No)), set(q.canned_answers.all()))
        result_Yes = q.get_canned_answer('Yes')
        self.assertEqual(result_Yes, t_Yes_expected)
        result_No = q.get_canned_answer('No')
        self.assertEqual(result_No, t_No_expected)
        self.assertNotEqual(result_Yes, result_No)

    def test_choice_get_canned_answer(self):
        q = QuestionFactory(section=self.section, input_type_id='choice')
        t_A_expected = 'ABC 123'
        t_A = CannedAnswerFactory(question=q, choice='A', canned_text=t_A_expected)
        t_B_expected = 'DEF 456'
        t_B = CannedAnswerFactory(question=q, choice='B', canned_text=t_B_expected)
        t_C_expected = 'GHI 789'
        t_C = CannedAnswerFactory(question=q, choice='C', canned_text=t_C_expected)
        self.assertEqual(set((t_A, t_B, t_C)), set(q.canned_answers.all()))
        result_A = q.get_canned_answer('A')
        self.assertEqual(result_A, t_A_expected)
        result_B = q.get_canned_answer('B')
        self.assertEqual(result_B, t_B_expected)
        result_C = q.get_canned_answer('C')
        self.assertEqual(result_C, t_C_expected)
        self.assertNotEqual(result_A, result_B)
        self.assertNotEqual(result_A, result_C)
        self.assertNotEqual(result_B, result_C)

    def test_multichoiceonetext_get_canned_answer(self):
        q = QuestionFactory(section=self.section, input_type_id='multichoiceonetext')
        t_A_expected = 'ABC 123'
        t_A = CannedAnswerFactory(question=q, choice='A', canned_text=t_A_expected)
        t_B_expected = 'DEF 456'
        t_B = CannedAnswerFactory(question=q, choice='B', canned_text=t_B_expected)
        t_C_expected = 'GHI 789'
        t_C = CannedAnswerFactory(question=q, choice='C', canned_text=t_C_expected)
        t_A_expected = 'ABC 123'
        self.assertEqual(set((t_A, t_B, t_C)), set(q.canned_answers.all()))
        result_A = q.get_canned_answer('A')
        self.assertEqual(result_A, 'A')
        result_many = q.get_canned_answer(['B', 'C'])
        expected = '{} and {}'.format('B', 'C')
        self.assertEqual(result_many, expected)

    def test_daterange_get_canned_answer(self):
        daterange = {'start': date(1980, 1, 1), 'end': date(1990, 1, 1)}
        text = 'From {start} to {end}'
        q = QuestionFactory(section=self.section, input_type_id='daterange', framing_text=text)
        expected = text.format(**daterange)
        result = q.get_canned_answer(daterange)
        self.assertEqual(result, expected)
