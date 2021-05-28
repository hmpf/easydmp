from django import test

from easydmp.dmpt.positioning import Move

from tests.dmpt.factories import TemplateFactory, SectionFactory


class TestTemplateMiscMethods(test.TestCase):

    def test_list_unknown_questions(self):
        template = TemplateFactory()
        SectionFactory(template=template, position=1)

        bad_ids = set((56, 565678587))  # No questions made so any id is bad
        data = dict(zip(bad_ids, bad_ids))
        result = template.list_unknown_questions(data)
        self.assertEqual(bad_ids, result)


class TestReorderSections(test.TestCase):

    def test_reorder_sections_from_template(self):
        template = TemplateFactory()
        top_section = SectionFactory(template=template, position=0)
        subsection1 = SectionFactory(template=template, super_section=top_section, section_depth=2, position=2)
        subsection2 = SectionFactory(template=template, super_section=top_section, section_depth=2, position=3)
        current_order = top_section.template.ordered_section_pks()
        top_section.reorder_sections(subsection1.pk, Move.DOWN)
        new_order = top_section.template.ordered_section_pks()
        self.assertNotEqual(current_order, new_order)
        self.assertEqual(new_order, [top_section.pk, subsection2.pk, subsection1.pk])
