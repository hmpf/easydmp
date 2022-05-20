import sys

from django.db import IntegrityError
from django.utils.timezone import now as tznow

from easydmp.eestore.models import EEStoreType, EEStoreSource, EEStoreCache

__all__ = ['fill_cache_from_class']


def fill_cache_from_class(cls, stderr=sys.stderr):
    """Fill the EEStore cache with items from a class

    The class is of the format

    class ClassName:
        etype: str = 'type name'
        source: str = 'source name'
        items: list = ['list', 'of', 'entries', 'to', 'cache']

    It is assumed that each item is in itself a persistent id, and it is used
    as-is in "name", "pid" and "remote_id".
    """
    try:
        et = EEStoreType.objects.create(name=cls.etype)
    except IntegrityError as e:
        stderr.write(f'"Type {cls.etype} alreday exists: {e}')
        et = EEStoreType.objects.get(name=cls.etype)

    try:
        esource = EEStoreSource.objects.create(eestore_type=et, name=cls.source)
    except IntegrityError as e:
        stderr.write(f'"Source {cls.source}" alreday exists: {e}')
        esource = EEStoreSource.objects.get(eestore_type=et, name=cls.source)
    timestamp = tznow()
    for i, item in enumerate(sorted(cls.items), start=1):
        eestore_pid = f'{cls.etype}:{cls.source}:{item}'
        try:
            ec = EEStoreCache.objects.create(
            eestore_type=et,
            source=esource,
            eestore_id=i,
            eestore_pid=eestore_pid,
            name=item,
            pid=item,
            remote_id=item,
            last_fetched=timestamp,
        )
        except IntegrityError as e:
            stderr.write(f'"{item}" alreday exists: {e}')

    return esource
