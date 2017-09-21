from datetime import date
from collections import OrderedDict

from django import test

from easydmp.dmpt.models import Template, Section, CannedAnswer, Question
from easydmp.dmpt.models import BooleanQuestion, ChoiceQuestion, DateRangeQuestion
from easydmp.dmpt.models import MultipleChoiceOneTextQuestion
from flow.models import Edge, Node, FSA


# def generate_questions(start, **canned_question):
#     s1 = BooleanQuestion.objects.create(label='s1', position=2, **canned_question)
#     s2 = ChoiceQuestion.objects.create(label='s2', position=3, **canned_question)
#     s3 = ChoiceQuestion.objects.create(label='s3', position=4, **canned_question)
#     s4 = ChoiceQuestion.objects.create(label='s4', position=5, **canned_question)
#     s5 = ChoiceQuestion.objects.create(label='s5', position=6, **canned_question)
#     questions = {
#         'start': start,
#         's1': s1,
#         's2': s2,
#         's3': s3,
#         's4': s4,
#         's5': s5,
#     }
#     srstart1 = Edge.objects.create(prev_node=start, next_node=s1)
#     sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
#     sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
#     sr24 = Edge.objects.create(prev_node=s2, next_node=s4)
#     sr34 = Edge.objects.create(prev_node=s3, next_node=s4)
#     sr45 = Edge.objects.create(prev_node=s4, next_node=s5)
#     sr5end = Edge.objects.create(prev_node=s5)
#     return questions
# 
# 
class CannedData(object):

    def setUp(self):
        self.template = Template.objects.create(title='Template')
        self.section = Section.objects.create(
            template=self.template,
            title='Miscellaneous',
            position=1,
        )
        self.canned_question = {
            'section': self.section,
            'question': 's',
        }
        self.canned_data = {
            'section': self.section,
            'template': self.template,
        }


class TestQuestionGetCannedAnswerMethods(CannedData, test.TestCase):

    def test_extra_fields_get_canned_answer(self):
        q = BooleanQuestion.objects.create(**self.canned_question)
        expected = ''
        result = q.get_canned_answer(True, foo='foo', bar='bar')
        self.assertEqual(result, expected)

    def test_bool_no_text_get_canned_answer(self):
        q = BooleanQuestion.objects.create(**self.canned_question)
        result = q.get_canned_answer(True)
        self.assertEqual(result, '')

    def test_bool_one_text_get_canned_answer(self):
        q = BooleanQuestion.objects.create(**self.canned_question)
        expected = 'ABC 123'
        t_TRUE = CannedAnswer.objects.create(
            question=q,
            canned_text=expected,
        )
        result_TRUE = q.get_canned_answer(True)
        self.assertEqual(result_TRUE, expected)
        result_whatever = q.get_canned_answer(False)
        self.assertEqual(result_whatever, expected)

    def test_bool_get_canned_answer(self):
        q = BooleanQuestion.objects.create(**self.canned_question)
        t_TRUE_expected = 'ABC 123'
        t_TRUE = CannedAnswer.objects.create(
            question=q,
            choice='Yes',
            canned_text=t_TRUE_expected,
        )
        t_FALSE_expected = 'DEF 456'
        t_FALSE = CannedAnswer.objects.create(
            question=q,
            choice='No',
            canned_text=t_FALSE_expected,
        )
        self.assertEqual(set((t_TRUE, t_FALSE)), set(q.canned_answers.all()))
        result_TRUE = q.get_canned_answer(True)
        self.assertEqual(result_TRUE, t_TRUE_expected)
        result_FALSE = q.get_canned_answer(False)
        self.assertEqual(result_FALSE, t_FALSE_expected)
        self.assertNotEqual(result_TRUE, result_FALSE)

    def test_choice_get_canned_answer(self):
        q = ChoiceQuestion.objects.create(**self.canned_question)
        t_A_expected = 'ABC 123'
        t_A = CannedAnswer.objects.create(
            question=q,
            choice='A',
            canned_text=t_A_expected,
        )
        t_B_expected = 'DEF 456'
        t_B = CannedAnswer.objects.create(
            question=q,
            choice='B',
            canned_text=t_B_expected,
        )
        t_C_expected = 'GHI 789'
        t_C = CannedAnswer.objects.create(
            question=q,
            choice='C',
            canned_text=t_C_expected,
        )
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
        q = MultipleChoiceOneTextQuestion.objects.create(**self.canned_question)
        t_A_expected = 'ABC 123'
        t_A = CannedAnswer.objects.create(
            question=q,
            choice='A',
            canned_text=t_A_expected,
        )
        t_B_expected = 'DEF 456'
        t_B = CannedAnswer.objects.create(
            question=q,
            choice='B',
            canned_text=t_B_expected,
        )
        t_C_expected = 'GHI 789'
        t_C = CannedAnswer.objects.create(
            question=q,
            choice='C',
            canned_text=t_C_expected,
        )
        self.assertEqual(set((t_A, t_B, t_C)), set(q.canned_answers.all()))
        result_A = q.get_canned_answer('A')
        self.assertEqual(result_A, 'A')
        result_many = q.get_canned_answer(['B', 'C'])
        expected = '{} and {}'.format('B', 'C')
        self.assertEqual(result_many, expected)

    def test_daterange_get_canned_answer(self):
        daterange = {'start': date(1980, 1, 1), 'end': date(1990, 1, 1)}
        text = 'From {start} to {end}'
        q = DateRangeQuestion.objects.create(
            framing_text=text,
            **self.canned_question
        )
        t = CannedAnswer.objects.create(
            question=q,
            canned_text=text,
        )
        expected = text.format(**daterange)
        result = q.get_canned_answer(daterange)
        self.assertEqual(result, expected)


class TestQuestionNextQuestionMethods(CannedData, test.TestCase):

    def test_no_next_question(self):
        q = DateRangeQuestion.objects.create(**self.canned_question)
        result = q.get_next_question(None)
        self.assertEqual(result, None)
        q = DateRangeQuestion.objects.create(position=2, **self.canned_question)
        result = q.get_next_question(None)
        self.assertEqual(result, None)

    def test_get_next_question(self):
        q1 = DateRangeQuestion.objects.create(position=1, **self.canned_question)
        q2 = ChoiceQuestion.objects.create(position=2, **self.canned_question)
        result = q1.get_next_question(None)
        self.assertEqual(result, q2)


class TestQuestionPrevQuestionMethods(CannedData, test.TestCase):

    def test_no_prev_question(self):
        q5 = DateRangeQuestion.objects.create(position=5, **self.canned_question)
        result = q5.get_prev_question()
        self.assertEqual(result, None)
        q1 = DateRangeQuestion.objects.create(position=1, **self.canned_question)
        result = q1.get_prev_question()
        self.assertEqual(result, None)

    def test_single_prevstate(self):
        q1 = DateRangeQuestion.objects.create(position=1, **self.canned_question)
        q2 = ChoiceQuestion.objects.create(position=2, **self.canned_question)
        result = q2.get_prev_question()
        self.assertEqual(result, q1)

#     def test_branching_nextstate(self):
#         s1 = BooleanQuestion.objects.create(name='S1', **self.canned_question)
#         s2 = ChoiceQuestion.objects.create(name='S2', **self.canned_question)
#         s3 = ChoiceQuestion.objects.create(name='S3', **self.canned_question)
#         sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
#         sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
#         with self.assertRaises(Edge.DoesNotExist):
#             result_None = s1.get_next_node({'S1': {'state': None}})
#         result_True = s1.get_next_node({'S1': {'state': True}})
#         self.assertEqual(result_True, s2)
#         result_False = s1.get_next_node({'S1': {'state': False}})
#         self.assertEqual(result_False, s3)
# 
#     def test_branching_depends_nextstate(self):
#         s0 = BooleanQuestion.objects.create(name='S0', **self.canned_question)
#         s1 = BooleanQuestion.objects.create(name='S1', depends=s0, **self.canned_question)
#         s2 = ChoiceQuestion.objects.create(name='S2', **self.canned_question)
#         s3 = ChoiceQuestion.objects.create(name='S3', **self.canned_question)
#         sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
#         sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
#         with self.assertRaises(Edge.DoesNotExist):
#             result_None = s1.get_next_node({'S0': {'state': None}})
#         result_True = s1.get_next_node({'S0': {'state': True}})
#         self.assertEqual(result_True, s2)
#         result_False = s1.get_next_node({'S0': {'state': False}})
#         self.assertEqual(result_False, s3)
# 
# 
# class TestQuestionPrevQuestionTestCase(CannedData, test.TestCase):
# 
#     def test_no_prevstate(self):
#         s = DateRangeQuestion.objects.create(name='S1', **self.canned_question)
#         result = s.get_prev_node(None)
#         self.assertEqual(result, None)
#         fsa = FSA.objects.create(name='Nada')
#         fsa.start = s
#         fsa.save()
#         sr = Edge.objects.create(next_node=s)
#         result = s.get_prev_node(None)
#         self.assertEqual(result, None)
# 
#     def test_single_prevstate(self):
#         s1 = DateRangeQuestion.objects.create(name='S1', **self.canned_question)
#         s2 = ChoiceQuestion.objects.create(name='S2', **self.canned_question)
#         sr = Edge.objects.create(prev_node=s1, next_node=s2)
#         result = s2.get_prev_node(None)
#         self.assertEqual(result, s1)
# 
#     def test_xor_multiple_prevstate(self):
#         """
#         s1 -> s2
#         s1 -> s3
#         s2 -> s4
#         s3 -> s4
#         """
#         s1 = BooleanQuestion.objects.create(name='S1', **self.canned_question)
#         s2 = ChoiceQuestion.objects.create(name='S2', **self.canned_question)
#         s3 = ChoiceQuestion.objects.create(name='S3', **self.canned_question)
#         s4 = ChoiceQuestion.objects.create(name='S4', **self.canned_question)
#         sr1 = Edge.objects.create(next_node=s1)
#         sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
#         sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
#         sr24 = Edge.objects.create(condition=False, prev_node=s2, next_node=s4)
#         sr34 = Edge.objects.create(condition=False, prev_node=s3, next_node=s4)
#         sr4end = Edge.objects.create(condition=False, prev_node=s4)
#         self.fsa.start = s1
#         self.fsa.save()
#         result_True = s4.get_prev_node({'S1': {'state': True}, 'S2': {'state': None}})
#         self.assertEqual(result_True, s2)
#         result_True = s4.get_prev_node({'S1': {'state': False}, 'S3': {'state': None}})
#         self.assertEqual(result_True, s3)
# 
#     def test_shortcut_multiple_prevstate(self):
#         """
#         s1 -> s2
#         s1 -> s3
#         s2 -> s3
#         """
#         s1 = BooleanQuestion.objects.create(name='S1', **self.canned_question)
#         s2 = ChoiceQuestion.objects.create(name='S2', **self.canned_question)
#         s3 = ChoiceQuestion.objects.create(name='S3', **self.canned_question)
#         sr1 = Edge.objects.create(next_node=s1)
#         sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
#         sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
#         sr23 = Edge.objects.create(prev_node=s2, next_node=s3)
#         sr3end = Edge.objects.create(condition=False, prev_node=s3)
#         self.fsa.start = s1
#         self.fsa.save()
#         result_True = s3.get_prev_node({'S1': {'state': True}, 'S2': {'state': None}})
#         self.assertEqual(result_True, s2)
#         result_False = s3.get_prev_node({'S1': {'state': False}})
#         self.assertEqual(result_False, s1)
# 
# 
# class TestFSA(CannedData, test.TestCase):
# 
#     def setUp(self):
#         super(TestFSA, self).setUp()
#         self.start = BooleanQuestion.objects.create(
#             name='START',
#             **self.canned_question
#         )
#         self.fsa.start = self.start
#         self.fsa.save()
# 
#     def generate_states(self):
#         self.states = generate_states(self.start, **self.canned_question)
# 
#     def test_get_states_per_section(self):
#         expected = [self.section.name, 'Things beloved by the emperor', 'Things that look like flies from a distance']
#         for i, name in enumerate(expected[1:]):
#             section = Section.objects.create(name=name, position=i, fsa=self.fsa)
#             state = Question.objects.create(name='S{}'.format(i), **self.canned_question)
#             state.section = section
#             state.save()
#         result = self.fsa.get_states_per_section()
#         self.assertEqual(list(result.keys()), expected)
#         self.assertEqual(type(result[self.section.name]), type([]))
# 
#     def test_generate_text(self):
#         self.maxDiff = None
#         self.generate_states()
#         t_START_text = 'Hulahoop'
#         t_S1_text = 'Huuba'
#         tstart = CannedAnswer.objects.create(state=self.start, text=t_START_text)
#         ts1 = CannedAnswer.objects.create(state=self.states['s1'], text=t_S1_text)
#         # Set bools to True
#         data = {}
#         for state in Question.objects.filter(fsa=self.fsa):
#             data[state.name] = {'state': True}
#         result = self.fsa.generate_text(data)
#         expected = [
#             {
#                 'section': self.section.name,
#                 'introductory_text': self.section.introductory_text,
#                 'paragraphs': [
#                     {'text': t_START_text, 'notes': ''},
#                     {'text': t_S1_text, 'notes': ''},
#                     {'notes': '', 'text': ''},
#                     {'notes': '', 'text': ''},
#                     {'notes': '', 'text': ''},
#                     {'notes': '', 'text': ''},
#                 ],
#             },
#         ]
#         self.assertEqual(result, expected)
