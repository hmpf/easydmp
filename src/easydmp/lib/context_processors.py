from django.conf import settings

from easydmp import __version__


def common(request):
    return {
        'version': __version__,
        'instance_message': getattr(settings, 'EASYDMP_INSTANCE_MESSAGE', ''),
        'is_production': getattr(settings, 'EASYDMP_PRODUCTION_INSTANCE', False),
    }
