from unittest import TestCase as UnitTestCase

from django.test import TestCase as DjangoTestCase

from easydmp.eestore.models import EEStoreCache, EEStoreType
from easydmp.rdadcs.models import RDADCSKey

# under test
from easydmp.rdadcs.lib.resources import load_rdadcs_eestore_cache_modelresource
from easydmp.rdadcs.lib.resources import load_rdadcs_keymapping_modelresource
from easydmp.rdadcs.lib.resources import load_rdadcs_template_dictresource


class TestModelResourceLoading(DjangoTestCase):

    def test_load_rdadcs_eestore_cache_modelresource(self):
        new_types = ('language', 'country', 'currency')
        for new_type in new_types:
            self.assertFalse(EEStoreType.objects.filter(name=new_type).exists())
        sources = [str(source.eestore_type)
                   for source in load_rdadcs_eestore_cache_modelresource()]
        self.assertEqual(set(new_types), set(sources))
        for new_type in new_types:
            count = EEStoreCache.objects.filter(eestore_type__name=new_type).count()
            self.assertGreater(count, 100)

    def test_load_rdadcs_keymapping_modelresource(self):
        count = RDADCSKey.objects.count()
        self.assertEqual(count, 0)
        load_rdadcs_keymapping_modelresource()
        count = RDADCSKey.objects.count()
        self.assertEqual(count, 93)


class TestNonModelResourceLoading(UnitTestCase):

    def test_load_rdadcs_template_dictresource(self):
        export_dict = load_rdadcs_template_dictresource()
        self.assertTrue(isinstance(export_dict, dict))
        self.assertTrue(export_dict)
