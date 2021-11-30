from datetime import datetime
import io
from uuid import uuid4

from django.utils.timezone import now as utcnow

default_app_config = 'easydmp.lib.apps.EasyDMPSiteConfig'

__all__ = [
    'deserialize_export',
    'dump_obj_to_searchable_string',
    'get_free_title_for_importing',
    'get_model_name',
    'iso_epoch',
    'pprint_list',
    'dump_obj_to_searchable_string',
    'deserialize_export',
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


# Why not just do str(obj)?
# Because this strips syntactic {[]} but retains them anywhere else
def dump_obj_to_searchable_string(obj):
    '''Dump anything readable in obj to a string

    This makes it possible to use string lookups and regular expessions on the
    obj.'''
    if not obj:
        return ''
    if isinstance(obj, str):
        return obj
    if isinstance(obj, datetime):
        # Support ISO8601 both with and without T
        return str(datetime) + ' ' + datetime.isoformat()
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out.append(dump_obj_to_searchable_string(k))
            out.append(dump_obj_to_searchable_string(v))
        return ' '.join(out)
    if isinstance(obj, (list, tuple)):
        return ' '.join([dump_obj_to_searchable_string(i) for i in obj])
    return str(obj)


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
    if serializer.is_valid(raise_exception=True):
        return data
    raise exception_type(f'{model_name} export is malformed')


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


def strip_model_dict(model_dict, *excluded_fields):
    always_exclude_fields = ['id', 'pk', 'cloned_from', 'cloned_when']
    for field in always_exclude_fields:
        model_dict.pop(field, None)
    for field in excluded_fields:
        model_dict.pop(field, None)
    return model_dict
