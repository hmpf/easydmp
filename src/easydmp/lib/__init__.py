from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    UTC = ZoneInfo('UTC')
except ImportError:
    from pytz import UTC

from django.utils.timezone import now as utcnow


default_app_config = 'easydmp.lib.apps.EasyDMPSiteConfig'

__all__ = [
    'UTC',
    'get_model_name',
    'iso_epoch',
    'pprint_list',
    'dump_obj_to_searchable_string',
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


def strip_model_dict(model_dict, *excluded_fields):
    always_exclude_fields = ['id', 'pk', 'cloned_from', 'cloned_when']
    for field in always_exclude_fields:
        model_dict.pop(field, None)
    for field in excluded_fields:
        model_dict.pop(field, None)
    return model_dict
