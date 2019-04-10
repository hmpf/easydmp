from unittest import TestCase
from unittest.mock import Mock, patch

from django.http import HttpResponseRedirect, HttpResponse
from django.test.client import RequestFactory

from easydmp.site.views import Homepage, LoginView


class HomepageTest(TestCase):

    def setUp(self):
        request = RequestFactory().get(path='/')
        self.request = request

    def test_get_authenticated(self):
        self.request.user = Mock()
        self.request.user.is_authenticated = Mock(return_value=True)
        result = Homepage().get(self.request)
        self.assertIsInstance(result, HttpResponseRedirect)

    def test_get_not_authenticated(self):
        self.request.user = Mock()
        self.request.user.is_authenticated = Mock(return_value=False)
        result = Homepage.as_view()(self.request)
        self.assertIsInstance(result, HttpResponse)


class LoginViewTest(TestCase):

    def test_get_context_data(self):
        result = LoginView().get_context_data()
        with patch('easydmp.site.views.TemplateView.get_context_data', return_value={}):
            self.assertIn('providers', result)
