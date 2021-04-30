from datetime import date
from collections import OrderedDict

from django import test

from easydmp.dmpt.utils import PositionUtils

from tests.dmpt.factories import (TemplateFactory, SectionFactory)


class TestSectionOrderingMethods(test.TestCase):

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


class TestPositionUtils(test.TestCase):

    def setUp(self):
        self.template = TemplateFactory()


class TestRenumberMixinViaTemplate(test.TestCase):

    def test_get_orderable_manager(self):
        template = TemplateFactory()
        manager = template.get_orderable_manager()
        self.assertEqual(manager, template.sections)

    def test_get_next_position_no_sections(self):
        template = TemplateFactory()
        result = template.get_next_position()
        self.assertEqual(result, 1)

    def test_get_next_position_some_sections(self):
        template = TemplateFactory()
        SectionFactory(template=template, position=1)
        result = template.get_next_position()
        self.assertEqual(result, 2)

    def test_set_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s3 = SectionFactory(template=template, position=3)
        old_order = [obj.pk for obj in template.sections.order_by('position')]
        new_order = [s1.pk, s3.pk, s2.pk]
        self.assertNotEqual(old_order, new_order)
        template.set_order(new_order)
        result = [obj.pk for obj in template.sections.order_by('position')]
        self.assertEqual(new_order, result)

    def test_get_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s3 = SectionFactory(template=template, position=3)
        expected = [s1.pk, s2.pk, s3.pk]
        result = template.get_order()
        self.assertEqual(expected, result)


class TestRenumberMixinViaSection(test.TestCase):

    def test_get_orderable_manager(self):
        template = TemplateFactory()
        section = SectionFactory(position=1, template=template)
        manager = section.get_orderable_manager()
        self.assertEqual(manager, section.subsections)

    def test_set_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s1_1 = SectionFactory(template=template, position=3,
                              super_section=s1, section_depth=2)
        old_order = [obj.pk for obj in template.sections.order_by('position')]
        new_order = [s1.pk, s1_1.pk, s2.pk]
        self.assertNotEqual(old_order, new_order)
        s1.set_order(new_order)
        result = [obj.pk for obj in template.sections.order_by('position')]
        self.assertEqual(new_order, result)

    def test_get_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s1_1 = SectionFactory(template=template, position=2,
                              super_section=s1, section_depth=2)
        s2 = SectionFactory(template=template, position=3)
        expected = [s1.pk, s1_1.pk, s2.pk]
        result = template.get_order()
        self.assertEqual(expected, result)
