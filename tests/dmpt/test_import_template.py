from unittest import TestCase as UnitTestCase
from django.test import TestCase as DjangoTestCase

from easydmp.dmpt.import_template import _prep_model_dict, _check_missing_input_types, TemplateImportError, _check_missing_eestore_types_and_sources, deserialize_template_export
from easydmp.dmpt.models import INPUT_TYPES

from tests.eestore.factories import EEStoreTypeFactory, EEStoreSourceFactory


class TestCheckMissingInputTypes(UnitTestCase):

    def test_no_input_types_in_use_should_succeed(self):
        testdict = {'input_types_in_use': []}
        result = _check_missing_input_types(testdict)
        self.assertEqual(result, None)

    def test_missing_input_types_in_use_should_raise_exception(self):
        missing = 'unknowntype:unknownsource'
        testdict = {'input_types_in_use': [missing]}
        with self.assertRaises(TemplateImportError) as e:
            result = _check_missing_input_types(testdict)
            self.assertTrue(missing in str(e))


class TestCheckMissingEEStoreTypesAndSources(DjangoTestCase):

    def test_no_eestore_mounts_should_succeed(self):
        result = _check_missing_eestore_types_and_sources(False)
        self.assertTrue(result is None)

    def test_no_eestore_types_should_fail(self):
        missing_type = 'unknowntype'
        eestore_mounts = [{
            'eestore_type': missing_type,
            'sources': []
        }]
        with self.assertRaises(TemplateImportError) as e:
            result = _check_missing_eestore_types_and_sources(eestore_mounts)
            self.assertTrue(missing_type in str(e))

    def test_no_eestore_sources_should_fail(self):
        eetype = EEStoreTypeFactory()
        missing_source = f'{eetype}:unknownsource'
        eestore_mounts = [{
            'eestore_type': str(eetype),
            'sources': [missing_source]
        }]
        with self.assertRaises(TemplateImportError) as e:
            result = _check_missing_eestore_types_and_sources(eestore_mounts)
            self.assertTrue(missing_source in str(e))

    def test_all_types_and_sources_found_should_succeed(self):
        eetype = EEStoreTypeFactory()
        eesource = EEStoreSourceFactory(eestore_type=eetype)
        eestore_mounts = [{
            'eestore_type': str(eetype),
            'sources': [str(eesource)]
        }]
        result = _check_missing_eestore_types_and_sources(eestore_mounts)
        self.assertTrue(result is None)
