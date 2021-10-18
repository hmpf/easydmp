from django import test

from easydmp.dmpt.models import ExplicitBranch
from easydmp.dmpt.positioning import Move

from tests.dmpt.factories import (TemplateFactory, SectionFactory,
                                  ReasonQuestionFactory)


class TestOrderingSection(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()

    def test_no_subsections_returns_section_in_list(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.ordered_sections()
        self.assertEqual(result, [section])
        self.assertEqual(self.template.ordered_sections(), [section])

    def test_subsections_returns_all_sections_in_flat_list(self):
        top_section = SectionFactory(template=self.template, position=1)
        subsection1 = SectionFactory(template=self.template, super_section=top_section, section_depth=2, position=5)
        subsection2 = SectionFactory(template=self.template, super_section=top_section, section_depth=2, position=25)
        result = top_section.ordered_sections()
        self.assertEqual(result, [top_section, subsection1, subsection2])
        subsubsection1 = SectionFactory(template=self.template, super_section=subsection1, section_depth=3, position=10)
        result = top_section.ordered_sections()
        self.assertEqual(result, [top_section, subsection1, subsubsection1, subsection2])
        self.assertEqual(self.template.ordered_sections(), [top_section, subsection1, subsubsection1, subsection2])


class TestReorderSections(test.TestCase):

    def test_reorder_sections_from_section(self):
        template = TemplateFactory()
        top_section = SectionFactory(template=template, position=1)
        subsection1 = SectionFactory(template=template, super_section=top_section, section_depth=2, position=2)
        subsection2 = SectionFactory(template=template, super_section=top_section, section_depth=2, position=3)
        current_order = top_section.template.ordered_section_pks()
        top_section.reorder_sections(subsection1.pk, Move.DOWN)
        new_order = top_section.template.ordered_section_pks()
        self.assertNotEqual(current_order, new_order)
        self.assertEqual(new_order, [top_section.pk, subsection2.pk, subsection1.pk])


class TestReorderQuestions(test.TestCase):

    def test_reorder_questions(self):
        template = TemplateFactory()
        section = SectionFactory(template=template, position=1)
        q1 = ReasonQuestionFactory(section=section)
        q2 = ReasonQuestionFactory(section=section)
        q3 = ReasonQuestionFactory(section=section)
        current_order = [obj.pk for obj in section.questions.order_by('position')]
        section.reorder_questions(q2.pk, Move.TOP)
        new_order = [obj.pk for obj in section.questions.order_by('position')]
        self.assertNotEqual(current_order, new_order)
        self.assertEqual(new_order, [q2.pk, q1.pk, q3.pk])


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
        parent = SectionFactory(template=self.template, super_section=grandparent, position=2)
        section = SectionFactory(template=self.template, super_section=parent, position=3)
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
        ReasonQuestionFactory(section=next_section)
        result = section.get_next_nonempty_section()
        self.assertEqual(result, next_section)

    def test_get_first_question_in_next_section_no_next_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_first_question_in_next_section()
        self.assertIsNone(result)

    def test_get_first_question_in_next_section(self):
        section = SectionFactory(template=self.template, position=1)
        next_section = SectionFactory(template=self.template, position=2)
        question = ReasonQuestionFactory(section=next_section)
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
        ReasonQuestionFactory(section=prev_section)
        result = section.get_prev_nonempty_section()
        self.assertEqual(result, prev_section)

    def test_get_last_question_in_prev_section_no_prev_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_question_in_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        question = ReasonQuestionFactory(section=prev_section)
        result = section.get_last_question_in_prev_section()
        self.assertEqual(result, question)

    def test_get_last_on_trunk_question_in_prev_section_no_prev_nonempty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_on_trunk_question_in_prev_section_no_prev_oblig_question(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        ReasonQuestionFactory(section=prev_section, on_trunk=False)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertIsNone(result)

    def test_get_last_on_trunk_question_in_prev_section(self):
        prev_section = SectionFactory(template=self.template, position=1)
        section = SectionFactory(template=self.template, position=2)
        question = ReasonQuestionFactory(section=prev_section, on_trunk=True)
        result = section.get_last_on_trunk_question_in_prev_section()
        self.assertEqual(result, question)

    def test_get_last_answered_question_empty_section(self):
        section = SectionFactory(template=self.template, position=1)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question_no_oblig_questions(self):
        section = SectionFactory(template=self.template, position=1)
        ReasonQuestionFactory(section=section, on_trunk=False)
        result = section.get_last_answered_question({})
        self.assertIsNone(result)

    def test_get_last_answered_question(self):
        # When testing that an answer exists, do not use a bare QuestionFactory
        # since an "answer" is only defined for Question subclasses
        section = SectionFactory(template=self.template, position=1)
        q1 = ReasonQuestionFactory(section=section, on_trunk=True, position=1)
        ReasonQuestionFactory(section=section, on_trunk=True, position=2)
        ReasonQuestionFactory(section=section, on_trunk=True, position=3)
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
        self.assertEqual('bool', q0.input_type_id)
        self.assertEqual(1, len(ExplicitBranch.objects.all()))
        branch = ExplicitBranch.objects.get()
        self.assertEqual('Last', branch.category)
        self.assertEqual(q0, branch.current_question)
        ReasonQuestionFactory(question='Foo', section=section, position=1).save()
        ReasonQuestionFactory(question='Bar', section=section, position=2).save()
        self.assertEqual(3, len(section.questions.all()))
        self.assertEqual(0, section.questions.first().position)

        section.optional = False
        section.save()
        self.assertEqual(0, len(ExplicitBranch.objects.all()))
        self.assertEqual(2, len(section.questions.all()))
        self.assertEqual(1, section.questions.get(question='Foo').position)
        self.assertEqual(2, section.questions.get(question='Bar').position)

    def test_optional_section_in_summary(self):
        # first section is optional
        section1 = SectionFactory.build(title='Section 1', template=self.template, position=1)
        section1.optional = True
        section1.save()
        q11 = ReasonQuestionFactory(question='Foo1', section=section1, position=1)
        q11.save()
        q12 = ReasonQuestionFactory(question='Bar1', section=section1, position=2)
        q12.save()
        # second section is required
        section2 = SectionFactory.build(title='Section 2', template=self.template, position=2)
        section2.optional = False
        section2.save()
        q21 = ReasonQuestionFactory(question='Foo2', section=section2, position=1)
        q21.save()
        q22 = ReasonQuestionFactory(question='Bar2', section=section2, position=2)
        q22.save()
        # third section is optional
        section3 = SectionFactory.build(title='Section 3', template=self.template, position=3)
        section3.optional = True
        section3.save()
        q31 = ReasonQuestionFactory(question='Foo3', section=section3, position=1)
        q31.save()
        q32 = ReasonQuestionFactory(question='Bar3', section=section3, position=2)
        q32.save()
        # there should be eight questions in all
        self.assertEqual(self.template.questions.count(), 8)

        # get summary from data set of answers
        s1_firstq_pk = section1.questions.all().first().pk
        s3_firstq_pk = section3.questions.all().first().pk
        data = {
            str(s1_firstq_pk): {"choice": "No"},
            str(q11.pk): {},
            str(q12.pk): {},
            str(s3_firstq_pk): {"choice": "Yes"},
            str(q31.pk): {},
            str(q32.pk): {},
        }
        summary = self.template.get_summary(data)
        self.assertEqual(1, len(summary[section1.title]['data']))
        self.assertEqual('(Template designer please update)', summary[section1.title]['data'][s1_firstq_pk]['question'].question)
        self.assertEqual(2, len(summary[section2.title]['data']))
        self.assertEqual(3, len(summary[section3.title]['data']))

    def test_get_optional_section_question_in_optional_section(self):
        section = SectionFactory.build(template=self.template, optional=True)
        section.save()
        question = section.get_optional_section_question()
        self.assertEqual(question.position, 0)
        self.assertEqual(question.input_type_id, 'bool')

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
