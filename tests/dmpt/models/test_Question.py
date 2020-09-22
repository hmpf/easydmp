from datetime import date
from collections import OrderedDict

from django import test

from easydmp.dmpt.flow import Transition, TransitionMap
from easydmp.dmpt.models import Template, Section, CannedAnswer, Question
from easydmp.dmpt.models import BooleanQuestion, ChoiceQuestion, DateRangeQuestion
from easydmp.dmpt.models import MultipleChoiceOneTextQuestion
from easydmp.dmpt.models import ExplicitBranch

from tests.dmpt.factories import (TemplateFactory, QuestionFactory,
                                  SectionFactory, BooleanQuestionFactory,
                                  ChoiceQuestionFactory, CannedAnswerFactory,
                                  ReasonQuestionFactory)


class CannedData(object):

    def setUp(self):
        self.template = TemplateFactory()
        self.section = SectionFactory(template=self.template, position=1)
        self.canned_question = {
            'section': self.section,
            'question': 's',
            'on_trunk': True,
        }
        self.canned_data = {
            'section': self.section,
            'template': self.template,
            'on_trunk': True,
        }


class TestGetCannedAnswerMethods(CannedData, test.TestCase):

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
        q = QuestionFactory(section=self.section, input_type='choice')
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
        q = QuestionFactory(section=self.section, input_type='multichoiceonetext')
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
        q = QuestionFactory(section=self.section, input_type='daterange', framing_text=text)
        expected = text.format(**daterange)
        result = q.get_canned_answer(daterange)
        self.assertEqual(result, expected)


class BranchingCannedData(CannedData):

    @staticmethod
    def create_single_question(section):
        q = ReasonQuestionFactory(question='Single', section=section, position=1)
        return q

    @staticmethod
    def create_two_linear_questions(section):
        q1 = ReasonQuestionFactory(
            question='First of two', section=section, position=1)
        q2 = ReasonQuestionFactory(
            question='Last of two', section=section, position=2)
        return (q1, q2)

    @staticmethod
    def create_shortcut(section):
        qstart = BooleanQuestionFactory(question='Take the shortcut?', section=section, position=1)
        qdetour = ReasonQuestionFactory(question='Detoured', section=section, position=2)
        qend = ReasonQuestionFactory(question='Reached destination', section=section, position=3)
        ExplicitBranch.objects.create(current_question=qstart, condition='Yes', category='CannedAnswer', next_question=qend)
        return (qstart, qdetour, qend)

    @staticmethod
    def create_shortcut_to_last(section):
        qstart = BooleanQuestionFactory(question='Take the shortcut?', section=section, position=1)
        qdetour = ReasonQuestionFactory(question='Detoured', section=section, position=2)
        ExplicitBranch.objects.create(current_question=qstart, condition='Yes', category='CannedAnswer', next_question=None)
        return (qstart, qdetour)

    @staticmethod
    def create_implicit_diamond(section):
        # Implicit diamond: one explicit branch, one repair branch
        # Note that qright and qleft cannot be on_trunk, or going backwards won't work
        qstart = ChoiceQuestionFactory(question='Choose direction:', section=section, position=1)
        qleft = ReasonQuestionFactory(question='Left', section=section, position=2, on_trunk=False)
        qright = ReasonQuestionFactory(question='Right', section=section, position=3, on_trunk=False)
        qend = ReasonQuestionFactory(question='End', section=section, position=4)
        ExplicitBranch.objects.create(current_question=qstart, condition='Right', category='CannedAnswer', next_question=qright)
        ExplicitBranch.objects.create(current_question=qleft, condition='', category='ExplicitBranch', next_question=qend)
        return (qstart, qleft, qright, qend)


class TestGenerateQuestionTransitionMap(BranchingCannedData, test.TestCase):

    def test_generate_transition_map_no_next_question(self):
        q = self.create_single_question(self.section)
        transition_map = q.generate_transition_map()
        self.assertEqual(len(transition_map), 1)
        expected_transition = Transition(current=q, choice=None, category='last', next=None)
        self.assertIn(expected_transition, transition_map.transitions)

    def test_generate_transition_map_linear(self):
        q1, q2 = self.create_two_linear_questions(self.section)
        transition_map = q1.generate_transition_map()
        self.assertEqual(len(transition_map), 1)
        expected_transition = Transition(current=q1, choice=None, category='position', next=q2)
        self.assertIn(expected_transition, transition_map.transitions)

    def test_generate_transition_map_shortcut(self):
        qstart, qdetour, qend = self.create_shortcut(self.section)
        transition_map = qstart.generate_transition_map()
        self.assertEqual(len(transition_map), 2)
        expected_transitions = set((
            Transition(category='CannedAnswer', current=qstart, choice='Yes', next=qend),
            Transition(category='position', current=qstart, choice=None, next=qdetour)
        ))
        self.assertEqual(expected_transitions, transition_map.transitions)

    def test_generate_transition_map_shortcut_to_last(self):
        qstart, qdetour = self.create_shortcut_to_last(self.section)
        transition_map = qstart.generate_transition_map()
        self.assertEqual(len(transition_map), 2)
        expected_transitions = set((
            Transition(category='CannedAnswer', current=qstart, choice='Yes', next=None),
            Transition(category='position', current=qstart, choice=None, next=qdetour)
        ))
        self.assertEqual(expected_transitions, transition_map.transitions)

    def test_generate_transition_map_implicit_diamond(self):
        qstart, qleft, qright, qend = self.create_implicit_diamond(self.section)

        # start
        transition_map_start = qstart.generate_transition_map()
        self.assertEqual(len(transition_map_start), 2)
        expected_transitions = set((
            Transition(category='CannedAnswer', current=qstart, choice='Right', next=qright),
            Transition(category='position', current=qstart, choice=None, next=qleft)
        ))
        self.assertEqual(expected_transitions, transition_map_start.transitions)

        # Right
        transition_map_right = qright.generate_transition_map()
        self.assertEqual(len(transition_map_right), 1)
        expected_transitions = set((
            Transition(category='position', current=qright, choice=None, next=qend),
        ))
        self.assertEqual(expected_transitions, transition_map_right.transitions)

        # Left
        transition_map_left = qleft.generate_transition_map()
        self.assertEqual(len(transition_map_left), 1)
        expected_transitions = set((
            Transition(category='ExplicitBranch', current=qleft, choice=None, next=qend),
        ))
        self.assertEqual(expected_transitions, transition_map_left.transitions)

class TestNextQuestionMethods(BranchingCannedData, test.TestCase):

    def test_get_next_question_no_next_question(self):
        q = self.create_single_question(self.section)
        result = q.get_next_question(None)
        self.assertEqual(result, None)

    def test_get_next_question_linear(self):
        q1, q2 = self.create_two_linear_questions(self.section)
        result = q1.get_next_question(None)
        self.assertEqual(result, q2)

    def test_get_next_question_shortcut(self):
        qstart, qdetour, qend = self.create_shortcut(self.section)

        # If qstart is "Yes", go to qend via ExplixcitBranch
        data = {str(qstart.pk): {'choice': 'Yes'}}
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, qend)

        # If qstart is "No", take the detour via implicit position
        data = {str(qstart.pk): {'choice': 'No'}}
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, qdetour)

    def test_get_next_question_shortcut_to_last(self):
        # Simplest possible branch
        qstart, qdetour = self.create_shortcut_to_last(self.section)

        # If qstart is "Yes", go directly to the end via ExplicitBranch
        data = {str(qstart.pk): {'choice': 'Yes'}}
        condition = qstart.get_condition(data)
        expected = 'Yes'
        self.assertEqual(condition, expected)
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, None)

        # If qstart is "No", take the detour via implicit position
        data = {str(qstart.pk): {'choice': 'No'}}
        condition = qstart.get_condition(data)
        expected = 'No'
        self.assertEqual(condition, expected)
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, qdetour)

    def test_get_next_question_implicit_diamond(self):
        qstart, qleft, qright, qend = self.create_implicit_diamond(self.section)

        # If qstart is "Right", go to qright via ExplicitBranch
        data = {str(qstart.pk): {'choice': 'Right'}}
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, qright)
        # After that should be qend
        qnext = qright.get_next_question(data)
        self.assertEqual(qnext, qend, "Right didn't go to End")

        # If qstart is "Left", go to qleft via position
        data = {str(qstart.pk): {'choice': 'Left'}}
        qnext = qstart.get_next_question(data)
        self.assertEqual(qnext, qleft)
        # After that should be qend
        qnext = qleft.get_next_question(data)
        self.assertEqual(qnext, qend, "Left didn't go to End")


class TestPrevQuestionMethods(BranchingCannedData, test.TestCase):

    def test_get_prev_question_no_prev_question(self):
        q = self.create_single_question(self.section)
        qprev = q.get_prev_question()
        self.assertEqual(qprev, None)

    def test_get_prev_question_linear(self):
        q1, q2 = self.create_two_linear_questions(self.section)
        qprev = q2.get_prev_question()
        self.assertEqual(qprev, q1)

    def test_get_prev_question_shortcut(self):
        qstart, qdetour, qend = self.create_shortcut(self.section)

        # If qstart is "Yes", go to qend via ExplixcitBranch
        data = {str(qstart.pk): {'choice': 'Yes'}}
        qprev = qend._get_prev_question_new(data)
        self.assertEqual(qprev, qstart)

        # If qstart is "No", take the detour via implicit position
        data = {str(qstart.pk): {'choice': 'No'}}
        qprev = qend._get_prev_question_new(data)
        self.assertEqual(qprev, qdetour)

    def test_get_prev_question_implicit_diamond(self):
        qstart, qleft, qright, qend = self.create_implicit_diamond(self.section)

        # If qstart is "Right", go to qright via ExplicitBranch
        data = {str(qstart.pk): {'choice': 'Right'}}
        qprev = qend._get_prev_question_new(data)
        self.assertEqual(qprev, qright, "End didn't go back to Right")
        # After that should be qstart
        qprev = qright._get_prev_question_new(data)
        self.assertEqual(qprev, qstart, "Right didn't go back to Start")

        # If qstart is "Left", go to qleft via position
        data = {str(qstart.pk): {'choice': 'Left'}}
        qprev = qend._get_prev_question_new(data)
        self.assertEqual(qprev, qleft, "End didn't go back to Left")
        # After that should be qend
        qprev = qleft._get_prev_question_new(data)
        self.assertEqual(qprev, qstart, "Left didn't go back to Start")
