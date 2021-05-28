from django import test

from easydmp.dmpt.utils import PositionUtils

from tests.dmpt.factories import (TemplateFactory, SectionFactory)


class TestRenumberMixinViaTemplate(test.TestCase):

    def test_set_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s3 = SectionFactory(template=template, position=3)
        old_order = [obj.pk for obj in template.sections.order_by('position')]
        new_order = [s1.pk, s3.pk, s2.pk]
        self.assertNotEqual(old_order, new_order)
        template.set_section_order(new_order)
        result = [obj.pk for obj in template.sections.order_by('position')]
        self.assertEqual(new_order, result)

    def test_get_order_no_subsections(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s3 = SectionFactory(template=template, position=3)
        expected = [s1.pk, s2.pk, s3.pk]
        result = template.get_section_order()
        self.assertEqual(expected, result)


class TestRenumberMixinViaSection(test.TestCase):

    def test_set_order(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s2 = SectionFactory(template=template, position=2)
        s1_1 = SectionFactory(template=template, position=3,
                              super_section=s1, section_depth=2)
        old_order = [obj.pk for obj in template.sections.order_by('position')]
        new_order = [s1.pk, s1_1.pk, s2.pk]
        self.assertNotEqual(old_order, new_order)
        s1.set_section_order(new_order)
        result = [obj.pk for obj in template.sections.order_by('position')]
        self.assertEqual(new_order, result)

    def test_get_order_ignore_subsections(self):
        template = TemplateFactory()
        s1 = SectionFactory(template=template, position=1)
        s1_1 = SectionFactory(template=template, position=2,
                              super_section=s1, section_depth=2)
        s2 = SectionFactory(template=template, position=3)
        expected = [s1.pk, s2.pk]
        result = template.get_section_order()
        self.assertEqual(expected, result)
