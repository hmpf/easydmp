import socket
import io
from uuid import uuid4

import requests
import requests.exceptions
from django.conf import settings
from django.utils.timezone import now as utcnow

from rest_framework.serializers import ValidationError

from easydmp.lib.api.response_exceptions import ServiceUnavailable


__all__ = [
    'DataImportError',
    'get_export_from_url',
    'deserialize_export',
    'get_free_title_for_importing',
    'get_origin',
]


CONNECT_TIMEOUT = 0.1
READ_TIMEOUT = 10
TIMEOUT_TUPLE = (CONNECT_TIMEOUT, READ_TIMEOUT)


class DataImportError(ValueError):
    pass


def get_export_from_url(url, deserialize_export):
    try:
        with requests.get(url, timeout=TIMEOUT_TUPLE) as response:
            response.raise_for_status()
            try:
                export_dict = deserialize_export(response.content)
                if export_dict:
                    return export_dict
            except DataImportError as e:
                raise ValidationError(e)
        raise ValidationError('Url points to invalid export, cannot import')
    except requests.exceptions.Timeout:
        raise ServiceUnavailable(
            detail=f'Could not access {url}, timeout'
        )


def deserialize_export(export_json, export_serializer, model_name, exception_type) -> dict:
    # If these are not imported here, drf can't find the plan-detail view (!)
    from rest_framework.parsers import JSONParser
    from rest_framework.exceptions import ParseError
    if isinstance(export_json, str):
        export_json = export_json.encode('utf-8')
    stream = io.BytesIO(export_json)
    try:
        data = JSONParser().parse(stream)
    except ParseError:
        raise exception_type(f'{model_name} export is not JSON')
    if not data:
        raise exception_type(f'{model_name} export is empty')
    serializer = export_serializer(data=data)
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError:
        raise exception_type(f'{model_name} export is malformed')
    return data


def get_free_title_for_importing(model_dict, origin, model):
    title = model_dict.pop('title')
    orig_pk = model_dict['id']
    if not model.objects.filter(title=title).exists():
        return title
    changed_title1 = f'{title} via {origin}#{orig_pk}'
    if not model.objects.filter(title=changed_title1).exists():
        return changed_title1
    changed_title2 = f'{changed_title1} at {utcnow()}'
    if not model.objects.filter(title=changed_title2).exists():
        return changed_title2
    return f'{changed_title2}, {uuid4()}'


def get_origin(origin=''):
    """Try to find a decent value for export "origin"

    From most to least explicit.
    """
    if origin:
        return origin
    settings_origin = getattr(settings, 'EASYDMP_ORIGIN', None)
    if settings_origin:
        return settings_origin
    # No explicit origin given
    # YAGNI? in case of no connection/no fqdn/public ip:
    # hash of secret key? uuid4?
    fqdns, ips = _get_net_info()
    if fqdns:
        return fqdns[0]
    if ips:
        return ips[0]
    return 'n/a'


# Why not just use socket.getfqdn? Well, it's *very* complicated.
# What you get differs between OSes, distros and sysadmin practice
# and "localhost" and private addresses are useless for what we need.
def _get_net_info(name=''):
    """Attempt to get all public ip-addresses and fqdns for localhost

    Returns two lists: one of fqdns and one of ips
    """
    name = name.strip()
    if not name or name == '0.0.0.0':
        name = socket.gethostname()
    try:
        addrs = socket.getaddrinfo(name, None, 0, socket.SOCK_DGRAM, 0,
                                   socket.AI_CANONNAME)
    except socket.error:
        return None, None

    fqdns = list()
    ips = list()
    for addr in addrs:
        ip = addr[4][0]
        fqdn = addr[3]
        if fqdn:
            fqdns.append(fqdn)
        if ip:
            ips.append(ip)
    return fqdns, ips
