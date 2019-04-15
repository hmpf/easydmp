from datetime import date
from collections import OrderedDict

from django import test

from easydmp.dmpt.flow import Transition, TransitionMap
from easydmp.dmpt.models import Template, Section, Question
from easydmp.dmpt.models import ExplicitBranch

from tests.dmpt.factories import (TemplateFactory, SectionFactory,
                                  QuestionFactory, ReasonQuestionFactory)


class TestMiscSectionMethods(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_get_topmost_section_no_parent(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_topmost_section()
        self.assertEqual(result, section)

    def test_get_topmost_section(self):
        # Because of (template, position) being UNIQUE, it is best to create
        # the topmost section first
        grandparent = SectionFactory(template=self.template, position=1)
        parent = SectionFactory(template=self.template, super_section=grandparent, position=1)
        section = SectionFactory(template=self.template, super_section=parent, position=1)
        result = section.get_topmost_section()
        self.assertEqual(result, grandparent)
        result = parent.get_topmost_section()
        self.assertEqual(result, grandparent)


class TestNextSectionMethods(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_get_all_next_sections_single_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_all_next_sections()
        self.assertFalse(bool(result))

    def test_get_all_next_sections_multiple_sections(self):
        section = SectionFactory(template=self.template, position=1)
        next_section = SectionFactory(template=self.template, position=2)
        result = section.get_all_next_sections()
        self.assertEqual(result[0], next_section)

    def test_get_next_section_no_next(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_next_section()
        self.assertIsNone(result)

    def test_get_next_section(self):
        section = SectionFactory(template=self.template, position=1)
        next_section = SectionFactory(template=self.template, position=2)
        result = section.get_next_section()
        self.assertEqual(result, next_section)

    def test_get_next_nonempty_section_no_next(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_next_nonempty_section()
        self.assertIsNone(result)

    def test_get_next_nonempty_section_only_empty_sections(self):
        section = SectionFactory(template=self.template, position=1)
        SectionFactory(template=self.template, position=2)
        result = section.get_next_nonempty_section()
        self.assertIsNone(result)

    def test_get_next_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        next_section = SectionFactory(template=self.template, position=2)
        QuestionFactory(section=next_section)
        result = section.get_next_nonempty_section()
        self.assertEqual(result, next_section)

    def test_get_first_question_in_next_section_no_next_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_first_question_in_next_section()
        self.assertIsNone(result)

    def test_get_first_question_in_next_section(self):
        section = SectionFactory(template=self.template, position=1)
        next_section = SectionFactory(template=self.template, position=2)
        question = QuestionFactory(section=next_section)
        result = section.get_first_question_in_next_section()
        self.assertEqual(result, question)


class TestPrevSectionMethods(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_get_all_prev_sections_single_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_all_prev_sections()
        self.assertFalse(bool(result))

    def test_get_all_prev_sections_multiple_sections(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        result = section.get_all_prev_sections()
        self.assertEqual(result[0], prev_section)

    def test_get_prev_section_no_prev(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_prev_section()
        self.assertIsNone(result)

    def test_get_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        result = section.get_prev_section()
        self.assertEqual(result, prev_section)

    def test_get_prev_nonempty_section_no_prev(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_prev_nonempty_section()
        self.assertIsNone(result)

    def test_get_prev_nonempty_section_only_empty_sections(self):
        SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        result = section.get_prev_nonempty_section()
        self.assertIsNone(result)

    def test_get_prev_nonempty_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        QuestionFactory(section=prev_section)
        result = section.get_prev_nonempty_section()
        self.assertEqual(result, prev_section)

    def test_get_last_question_in_prev_section_no_prev_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_question_in_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        question = QuestionFactory(section=prev_section)
        result = section.get_last_question_in_prev_section()
        self.assertEqual(result, question)

    def test_get_last_obligatory_question_in_prev_section_no_prev_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_obligatory_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_obligatory_question_in_prev_section_no_prev_oblig_question(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        QuestionFactory(section=prev_section, obligatory=False)
        result = section.get_last_obligatory_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_obligatory_question_in_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        question = QuestionFactory(section=prev_section, obligatory=True)
        result = section.get_last_obligatory_question_in_prev_section()
        self.assertEqual(result, question)

    def test_get_last_answered_question_empty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question_no_oblig_questions(self):
        section = SectionFactory(template=self.template, position=1)
        q2 = QuestionFactory(section=section, obligatory=False)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question(self):
        # When testing that an answer exists, do not use a bare QuestionFactory
        # since an "answer" is only defined for Question subclasses
        section = SectionFactory(template=self.template, position=1)
        q1 = ReasonQuestionFactory(section=section, obligatory=True, position=1)
        q2 = ReasonQuestionFactory(section=section, obligatory=True, position=2)
        q3 = ReasonQuestionFactory(section=section, obligatory=True, position=3)
        answers = {
            str(q1.id): 'foo',
        }
        result = section.get_last_answered_question(answers)
        self.assertEqual(result, q1)
