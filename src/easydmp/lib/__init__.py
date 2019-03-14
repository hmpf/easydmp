import socket

from django.conf import settings
from django.utils.timezone import now as utcnow


__all__ = [
    'pprint_list',
    'iso_epoch',
    'get_origin_site',
]


def pprint_list(list_):
    if not list_:
        return u''
    if len(list_) == 1:
        return list_[0]
    first_part = ', '.join(list_[:-1])
    return '{} and {}'.format(first_part, list_[-1])


def utc_epoch(utc_datetime=None):
    if not utc_datetime:
        utc_datetime = utcnow()
    return utc_datetime.timestamp()


def get_model_name(model):
    return model._meta.model_name


def generate_default_permission_strings(model_name):
    perms = []
    for perm in ('add', 'change', 'delete'):
        perms.append('{}_{}'.format(perm, model_name))
    return perms


def get_origin_site(request=None):
    """Try to get something usable as a unique origin site

    Use the setting ORIGIN_SITE if it exists. If not check if the hostname in
    the request is sensible. If it is localhost or not an ip address or not
    a fully qualified domain name, generate a unique id.
    """
    default_host = settings.get('ORIGIN_SITE', None)
    port = ''
    if default_host:
        return default_host
    if request:
        host = get_hostname_from_request(request)
        if ':' in host:
            host, port = host.rsplit(':')
    if host in ('localhost', '127.0.0.1', '::1'):
        host = socket.getfqdn()
        LOG.warn('Could not find a sensible origin site, will try to use hostname {}'.format(host))
    if not '.' in host:
        host = uuid4().hex
        LOG.warn('Could not find a sensible origin site, using {}'.format(host))
    return host


def get_hostname_from_request(request):
    """Try to get domain and port as seen by the user"""
    if not request:
        return
    host = ''
    port = ''
    try:
        host = request.get_host()
    except DisallowedHost:
        return
    port = request.get_port()
    if port in ('80', '433'):
        return host
    return '{}:{}'.format(host, port)
