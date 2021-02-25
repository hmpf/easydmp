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


class TestOrderedSectionsMethod(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_no_subsections_returns_section_in_list(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.ordered_sections()
        self.assertEqual(result, [section])
        self.assertEqual(self.template.ordered_sections(), [section])

    def test_subsections_returns_all_sections_in_flat_list(self):
        top_section = SectionFactory(template=self.template, position=1)
        subsection1 = SectionFactory(template=self.template, super_section=top_section, section_depth=2, position=1)
        subsection2 = SectionFactory(template=self.template, super_section=top_section, section_depth=2, position=2)
        result = top_section.ordered_sections()
        self.assertEqual(result, [top_section, subsection1, subsection2])
        subsubsection1 = SectionFactory(template=self.template, super_section=subsection1, section_depth=3, position=1)
        result = top_section.ordered_sections()
        self.assertEqual(result, [top_section, subsection1, subsubsection1, subsection2])
        self.assertEqual(self.template.ordered_sections(), [top_section, subsection1, subsubsection1, subsection2])


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

    def test_get_last_on_trunk_question_in_prev_section_no_prev_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_on_trunk_question_in_prev_section_no_prev_oblig_question(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        QuestionFactory(section=prev_section, on_trunk=False)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_on_trunk_question_in_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        question = QuestionFactory(section=prev_section, on_trunk=True)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertEqual(result, question)

    def test_get_last_answered_question_empty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question_no_oblig_questions(self):
        section = SectionFactory(template=self.template, position=1)
        q2 = QuestionFactory(section=section, on_trunk=False)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question(self):
        # When testing that an answer exists, do not use a bare QuestionFactory
        # since an "answer" is only defined for Question subclasses
        section = SectionFactory(template=self.template, position=1)
        q1 = ReasonQuestionFactory(section=section, on_trunk=True, position=1)
        q2 = ReasonQuestionFactory(section=section, on_trunk=True, position=2)
        q3 = ReasonQuestionFactory(section=section, on_trunk=True, position=3)
        answers = {
            str(q1.id): 'foo',
        }
        result = section.get_last_answered_question(answers)
        self.assertEqual(result, q1)


class TestOptionalSections(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_optional_question_added(self):
        section = SectionFactory(position=1)
        section.optional = True
        section.save()
        self.assertEqual(1, len(section.questions.all()))
        q0 = section.questions.get()
        self.assertEqual(0, q0.position)
        self.assertEqual('bool', q0.input_type)
        self.assertEqual(1, len(ExplicitBranch.objects.all()))
        branch = ExplicitBranch.objects.get()
        self.assertEqual('Last', branch.category)
        self.assertEqual(q0, branch.current_question)
        Question(question='Foo', section=section, position=1).save()
        Question(question='Bar', section=section, position=2).save()
        self.assertEqual(3, len(section.questions.all()))
        self.assertEqual(0, section.questions.first().position)

        section.optional = False
        section.save()
        self.assertEqual(0, len(ExplicitBranch.objects.all()))
        self.assertEqual(2, len(section.questions.all()))
        self.assertEqual(1, section.questions.get(question='Foo').position)
        self.assertEqual(2, section.questions.get(question='Bar').position)

    def test_optional_section_in_summary(self):
        section0 = SectionFactory.build(template=self.template, position=1)
        section0.optional = True
        section0.save()
        q01 = Question(question='Foo', section=section0, position=1)
        q01.save()
        q02 = Question(question='Bar', section=section0, position=2)
        q02.save()
        section1 = SectionFactory.build(template=self.template, position=2)
        section1.optional = False
        section1.save()
        Question(question='Foo', section=section1, position=1).save()
        Question(question='Bar', section=section1, position=2).save()
        section2 = SectionFactory.build(template=self.template, position=3)
        section2.optional = True
        section2.save()
        q21 = Question(question='Foo2', section=section2, position=1)
        q21.save()
        q22 = Question(question='Bar2', section=section2, position=2)
        q22.save()

        # get summary from data set of answers
        s0_firstq_pk = section0.questions.all().first().pk
        s2_firstq_pk = section2.questions.all().first().pk
        summary = self.template.get_summary({str(s0_firstq_pk): {"choice": "No"},
                                             str(q01.pk): {},
                                             str(q02.pk): {},
                                             str(s2_firstq_pk): {"choice": "Yes"},
                                             str(q21.pk): {},
                                             str(q22.pk): {},
                                             })
        self.assertEqual(1, len(summary[section0.title]['data']))
        self.assertEqual('(Template designer please update)', summary[section0.title]['data'][s0_firstq_pk]['question'].question)
        self.assertEqual(2, len(summary[section1.title]['data']))
        self.assertEqual(3, len(summary[section2.title]['data']))

    def test_get_optional_section_question_in_optional_section(self):
        section = SectionFactory.build(template=self.template, optional=True)
        section.save()
        question = section.get_optional_section_question()
        self.assertEqual(question.position, 0)
        self.assertEqual(question.input_type, 'bool')

    def test_get_optional_section_question_in_normal_section(self):
        section = SectionFactory.build(template=self.template, optional=False)
        section.save()
        question = section.get_optional_section_question()
        self.assertEqual(question, None)

    def test_is_skipped_true(self):
        section = SectionFactory.build(template=self.template, optional=True)
        section.save()
        toggle_question = section.get_optional_section_question()
        data = {str(toggle_question.pk): {'choice': 'No'}}
        result = section.is_skipped(data)
        self.assertTrue(result)

    def test_is_skipped_when_not_answered_is_true(self):
        section = SectionFactory.build(template=self.template, optional=True)
        section.save()
        toggle_question = section.get_optional_section_question()
        data = {}
        result = section.is_skipped(data)
        self.assertTrue(result)

    def test_is_skipped_on_normal_section_is_false(self):
        section = SectionFactory.build(template=self.template, optional=False)
        section.save()
        result = section.is_skipped(None)
        self.assertFalse(result)

    def test_is_skipped_false(self):
        section = SectionFactory.build(template=self.template, optional=True)
        section.save()
        toggle_question = section.get_optional_section_question()
        data = {str(toggle_question.pk): {'choice': 'Yes'}}
        result = section.is_skipped(data)
        self.assertFalse(result)
