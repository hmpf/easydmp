from django.conf import settings
from django.shortcuts import render
from django.utils.cache import add_never_cache_headers
from django.utils.deprecation import MiddlewareMixin


class MaintenanceModeMiddleware(MiddlewareMixin):

    def process_request(self, request):
        if not getattr(settings, 'MAINTENANCE_MODE', None):
            return None

        response = render(request, '503.html', content_type='text/html', status=503)
        add_never_cache_headers(response)
        return response
