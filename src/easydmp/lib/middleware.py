from django.conf import settings
from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin


class MaintenanceModeMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'MAINTENANCE_MODE', None):
            return self.get_response(request)

        response = render(request, '503.html', content_type='text/html', status=503)
        add_never_cache_headers(response)
        return response
