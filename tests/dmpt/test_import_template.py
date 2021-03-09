import json
from unittest import TestCase as UnitTestCase

from django.test import TestCase as DjangoTestCase
from django.test import tag

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


@tag('unittest')
class TestDeserilizeTemplateExport(UnitTestCase):

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
        data = {
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
              ]
            },
            "template": {
              "id": 64,
              "modified": "2021-02-25T08:35:00.817527Z",
              "cloned_from": None,
              "cloned_when": None,
              "title": "Section examples",
              "abbreviation": "",
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
              ]
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
                "repeatable": False
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
                "optional_canned_text": ""
              },
            ],
            "explicit_branches": [],
            "canned_answers": [],
            "eestore_mounts": [],
        }
        jsonblob = json.dumps(data)
        result = deserialize_template_export(jsonblob)
        self.assertEqual(data, result)

