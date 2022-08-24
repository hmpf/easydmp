from unittest.mock import Mock

from django import test
from django.http import HttpResponseRedirect
from django.test.client import RequestFactory

from easydmp.lib.middleware import MaintenanceModeMiddleware


class TestMaintenanceModeMiddleware(test.TestCase):

    def test_maintenance_mode_is_off(self):
        request = RequestFactory().get('/foo')
        response = MaintenanceModeMiddleware(lambda x: x)(request)
        # Do nothing
        self.assertEqual(response, request)

    @test.override_settings(MAINTENANCE_MODE=True)
    def test_maintenance_mode_is_on(self):
        request = RequestFactory().get('/foo')
        response = MaintenanceModeMiddleware(lambda x: x)(request)
        self.assertEqual(response.status_code, 503)
