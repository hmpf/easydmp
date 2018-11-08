from django.utils.timezone import now as utcnow


__all__ = [
    'pprint_list',
    'iso_epoch',
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
