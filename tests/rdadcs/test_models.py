import unittest

from django import test

from easydmp.rdadcs.models import RDADCSKey, RDADCSQuestionLink


class TestRDADCSKey(test.TestCase):

    def test_str(self):
        path = '.bear.yogi.berra'
        key = RDADCSKey(path=path)
        key.save()
        expected_result = 'yogi berra'
        actual_result = str(key)
        self.assertEqual(expected_result, actual_result)

    def test_save(self):
        path = '.bear.yogi.berra'
        key = RDADCSKey(path=path)
        key.save()
        self.assertFalse(key.optional)
        self.assertFalse(key.repeatable)
        self.assertEqual(path, key.path)
        self.assertEqual('1-bear-yogi-berra', key.slug)


class TestRDADCCSKeySlugifyPath(unittest.TestCase):

    def test_slugify_path(self):
        expected_result = '1-foo-bar'
        path = '.foo.bar'
        actual_result = RDADCSKey.slugify_path(path)
        self.assertEqual(expected_result, actual_result)


class TestRDADCCSKeyParseKey(unittest.TestCase):
    # Golden path
    def test_parse_obligatory_single_key(self):
        expected_result = 'berra', False, False
        key = 'berra'
        actual_result = RDADCSKey.parse_key(key)
        self.assertEqual(expected_result, actual_result)

    def test_parse_obligatory_multi_key(self):
        expected_result = 'berra', False, True
        key = 'berra[]'
        actual_result = RDADCSKey.parse_key(key)
        self.assertEqual(expected_result, actual_result)

    def test_parse_optional_single_key(self):
        expected_result = 'berra', True, False
        key = 'berra?'
        actual_result = RDADCSKey.parse_key(key)
        self.assertEqual(expected_result, actual_result)

    def test_parse_optional_multi_key(self):
        expected_result = 'berra', True, True
        key = 'berra[]?'
        actual_result = RDADCSKey.parse_key(key)
        self.assertEqual(expected_result, actual_result)

    # Invalid keys
    def test_empty_key_should_fail(self):
        key = ''
        with self.assertRaises(IndexError):
            RDADCSKey.parse_key(key)


class TestRDADCSKeyGetKey(unittest.TestCase):

    def test_valid_path_should_return_final_key(self):
        expected_result = 'berra'
        key = '.yogi.berra[]?'
        actual_result, *_ = RDADCSKey.get_key(key)
        self.assertEqual(expected_result, actual_result)

    def test_key_not_starting_with_dot_should_fail(self):
        key = 'berra[]?'
        with self.assertRaises(ValueError):
            RDADCSKey.get_key(key)
