from unittest import TestCase as UnitTestCase
from django.test import TestCase as DjangoTestCase, override_settings

from easydmp.dmpt.export_template import ExportSerializer, serialize_template_export

from tests.dmpt.factories import *

VERSION = 'blbl'


def create_minimum_template():
    template = TemplateFactory()
    section = SectionFactory(template=template, position=1)
    question = QuestionFactory(input_type='shortfreetext', section=section, position=1)
    return template


@override_settings(VERSION=VERSION)
class TestSerializeTemplateExport(DjangoTestCase):

    def test_serialize_template_export_should_return_drf_serializer(self):
        template = create_minimum_template()
        result = serialize_template_export(template.pk)
        self.assertTrue(isinstance(result, ExportSerializer))

    def test_ExportSerializer_data_should_be_of_a_certain_structure(self):
        template = create_minimum_template()
        serializer = serialize_template_export(template.pk)
        keys = {'comment', 'easydmp', 'template', 'sections', 'questions', 'canned_answers', 'explicit_branches', 'eestore_mounts'}
        self.assertEqual(keys, set(serializer.data.keys()))
        self.assertEqual(serializer.data['easydmp']['version'], VERSION)
