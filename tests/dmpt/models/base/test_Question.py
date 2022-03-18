from django import test

from easydmp.dmpt.flow import Transition
from easydmp.dmpt.models import ExplicitBranch
from easydmp.dmpt.positioning import Move

from tests.dmpt.factories import (
    TemplateFactory,
    SectionFactory,
    BooleanQuestionFactory,
    ChoiceQuestionFactory,
    ShortFreetextQuestionFactory,
    ReasonQuestionFactory,
    CannedAnswerFactory,
)


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


class TestReorderCannedAnswers(test.TestCase):

    def test_reorder_canned_answers(self):
        template = TemplateFactory()
        section = SectionFactory(template=template, position=1)
        # Three canned answers automatically made
        question = ChoiceQuestionFactory(section=section)
        current_order = [obj.pk for obj in question.canned_answers.order_by('position')]
        question.reorder_canned_answers(current_order[1], Move.TOP)
        new_order = [obj.pk for obj in question.canned_answers.order_by('position')]
        self.assertNotEqual(current_order, new_order)
        self.assertEqual(new_order, [current_order[1], current_order[0], current_order[2]])


class TestIdentifyingQuestions(CannedData, test.TestCase):

    def test_shortfreetext_can_be_an_identifier(self):
        stf = ShortFreetextQuestionFactory(section=self.section)
        self.assertTrue(stf.can_identify)
        answer = 'bghjk'
        self.assertEqual(answer, stf.get_identifier(answer))

    def test_most_questions_cannot_be_an_identifier(self):
        reason = ReasonQuestionFactory(section=self.section)
        self.assertFalse(reason.can_identify)
        with self.assertRaises(NotImplementedError):
            reason.get_identifier('vfbgnhj')
