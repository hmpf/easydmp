from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase as UnitTestCase
from importlib.resources import read_text

from django.test import TestCase as DjangoTestCase
from django.test import tag
from django.test import override_settings

from easydmp.dmpt.import_template import _check_missing_eestore_types_and_sources
from easydmp.dmpt.import_template import _check_missing_input_types
from easydmp.dmpt.import_template import deserialize_template_export
from easydmp.dmpt.import_template import import_or_get_template
from easydmp.dmpt.import_template import TemplateImportError
from easydmp.rdadcs.lib.resources import load_rdadcs_eestore_cache_modelresource
from easydmp.rdadcs.lib.resources import load_rdadcs_keymapping_modelresource
from easydmp.rdadcs.lib.resources import load_rdadcs_template_dictresource

from tests.eestore.factories import EEStoreTypeFactory, EEStoreSourceFactory


EXPORT_DICT = {
    "comment": "",
    "easydmp": {
      "version": "1.5.0",
      "origin": "examples",
      "input_types": [
        "bool",
        "choice",
        "date",
        "daterange",
        "extchoicenotlisted",
        "externalchoice",
        "externalmultichoiceonetext",
        "extmultichoicenotlistedonetext",
        "multichoiceonetext",
        "multidmptypedreasononetext",
        "multinamedurlonetext",
        "multirdacostonetext",
        "namedurl",
        "positiveinteger",
        "reason",
        "shortfreetext",
        "storageforecast"
      ],
    },
    "template": {
      "id": 64,
      "modified": "2021-02-25T08:35:00.817527Z",
      "cloned_from": None,
      "cloned_when": None,
      "title": "Section examples",
      "abbreviation": "",
      "uuid": "91e211b3-93df-4156-a8b7-6ef56d3a7b3b",
      "description": "",
      "more_info": "",
      "domain_specific": False,
      "reveal_questions": False,
      "version": 1,
      "created": "2021-02-25T08:35:00.817581Z",
      "published": None,
      "retired": None,
      "input_types_in_use": [
        "reason"
      ],
      "rdadcs_keys_in_use": [],
    },
    "sections": [
      {
        "id": 184,
        "modified": "2021-02-25T08:35:25.391259Z",
        "cloned_from": None,
        "cloned_when": None,
        "template": 64,
        "label": "",
        "title": "A section, required",
        "position": 1,
        "introductory_text": "",
        "comment": "",
        "super_section": None,
        "section_depth": 1,
        "branching": False,
        "optional": False,
        "repeatable": False,
        "identifier_question": None,
        "rdadcs_path": None,
      },
    ],
    "questions": [
                      {
        "id": 625,
        "cloned_from": None,
        "cloned_when": None,
        "input_type": "reason",
        "section": 184,
        "position": 1,
        "label": "",
        "question": "A q req",
        "help_text": "",
        "framing_text": "",
        "comment": "",
        "on_trunk": True,
        "optional": False,
        "optional_canned_text": "",
        "rdadcs_path": None,
      },
    ],
    "explicit_branches": [],
    "canned_answers": [],
    "eestore_mounts": [],
}
RDADCS_TEMPLATE = 'rdadcs-v1.1.template.json'


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


@tag('unittest')
class TestDeserializeTemplateExport(UnitTestCase):

    def test_garbage_should_fail(self):
        with self.assertRaises(TemplateImportError) as e:
            deserialize_template_export('vbgfnhj')
            self.assertEqual(str(e), 'Template export is not JSON')

    def test_empty_should_fail(self):
        with self.assertRaises(TemplateImportError) as e:
            deserialize_template_export('{}')
            self.assertEqual(str(e), 'Template export is empty')

    def test_malformed_should_fail(self):
        with self.assertRaises(TemplateImportError) as e:
            deserialize_template_export('{"a": 1}')
            self.assertEqual(str(e), 'Template export is malformed')

    def test_valid_should_succeed(self):
        data = deepcopy(EXPORT_DICT)
        jsonblob = json.dumps(data)
        result = deserialize_template_export(jsonblob)
        self.assertEqual(data, result)


@override_settings(VERSION='blbl')
class TestImportOrGetTemplate(DjangoTestCase):

    def test_import_serialized_template_export_with_one_section(self):
        export_dict = deepcopy(EXPORT_DICT)
        tim = import_or_get_template(export_dict, via='test')
        # ensure mappings are of the right format by reloading the tim
        tim.refresh_from_db()  # int -> str after save
        mappings = tim.mappings
        self.assertIn('184', mappings['sections'])
        self.assertTrue(mappings['sections']['184'])
        self.assertEqual(mappings['sections']['184'], 1)
        self.assertIn('625', mappings['questions'])
        self.assertTrue(mappings['questions']['625'])
        self.assertEqual(mappings['questions']['625'], 1)

    def test_import_rdadcs_with_import_serialized_template_export(self):
        # fixtures
        tuple(load_rdadcs_eestore_cache_modelresource())
        load_rdadcs_keymapping_modelresource()
        complex_export_dict = load_rdadcs_template_dictresource()

        export_dict = deepcopy(complex_export_dict)
        tim = import_or_get_template(export_dict, via='test')
        # ensure mappings are of the right format by reloading the tim
        tim.refresh_from_db()  # int -> str after save
        mappings = tim.mappings

    def test_importing_twice_does_not_create_two_templates(self):
        export_dict = deepcopy(EXPORT_DICT)
        tim1 = import_or_get_template(export_dict, via='test')
        tim1.refresh_from_db()
        export_dict = deepcopy(EXPORT_DICT)
        tim2 = import_or_get_template(export_dict, via='test')
        tim2.refresh_from_db()
        self.assertEqual(tim1, tim2)
