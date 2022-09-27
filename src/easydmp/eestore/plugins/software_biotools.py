import requests

from easydmp.eestore.models import EEStoreCache
from easydmp.eestore.plugins.utils import parse_datetime
from easydmp.eestore.plugins.utils import get_source
from easydmp.eestore.plugins import utils


__all__ = [
    'refetch_entries',
]


TYPE = 'software'
SOURCE = 'biotools'
ENDPOINT = 'https://bio.tools/api/tool/'
_sourcestring = f'{TYPE}:{SOURCE}'


def get_next(jsonblob):
    next_url = jsonblob['next']
    return next_url.rsplit('=', 1)[-1] if next_url else None


def get_entries(jsonblob):
    return jsonblob["list"]


def get_page(session, params, get_entries, get_next):
    r = requests.get(ENDPOINT, params=params)
    if r.status_code != requests.codes.ok:
        return None
    jsonblob = r.json()
    entries = get_entries(jsonblob)
    next = get_next(jsonblob)
    return entries, next


def get_pages(last_fetched=None, verbose=False):
    params = {'format': 'json'}
    if last_fetched:
        params['sort'] = 'lastUpdate'
        params['ord'] = 'desc'
    else:
        params['sort'] = 'name'
        params['ord'] = 'asc'
    session = requests.Session()
    next = 1
    stop = False
    while next and not stop:
        params['page'] = next
        raw_entries, next = get_page(session, params, get_entries, get_next)
        entries, stop = utils.convert_page(raw_entries, extract_entry, last_fetched)
        if verbose:
            print(f'Page #{next}')
            print(entries[-1])
            print()
        yield entries


def extract_entry(jsonblob, last_fetched=None):
    "Extract eestore software entry from biotools"

    updated = jsonblob['lastUpdate']
    if last_fetched and parse_datetime(updated) < last_fetched:
        return None
    remote_id = jsonblob['biotoolsID']
    entry = {
        'eestore_pid': f'{TYPE}:{SOURCE}:{remote_id}',
        'name': jsonblob['name'],
        'pid': jsonblob['biotoolsCURIE'],
        'remote_id': remote_id,
        'uri': jsonblob.get('homepage', ''),
        'last_fetched': updated,
        'data': {
            'created': jsonblob['additionDate'],
        }
    }
    return entry


def store_pages(OutFile, last_fetched=None, verbose=None):
    try:
        for entries in get_pages(last_fetched, verbose):
            utils.store_entries(entries, OutFile)
    finally:
        OutFile.close()


def update_entries(entries):
    new_id_map = {e['pid']: e for e in entries}
    del entries
    source = get_source()
    cached_entries = source.records.all()
    latest = cached_entries.order_by('-eestore_id').first()
    old_id_map = {e['pid']: e for e in cached_entries.values()}
    del cached_entries
    new_entries = []
    changed_entries = []
    for pid, entry in new_id_map.items():
        old_entry = old_id_map.get(pid, None)
        if old_entry:
            changed_entries.append((old_entry, entry))
        else:
            new_entries.append(entry)
    if new_entries:
        utils.create_entries(source, new_entries, start=latest.eestore_id+1)
    for old, new in changed_entries:
        new['last_fetched'] = parse_datetime(new['last_fetched'])
        EEStoreCache.objects.filter(eestore_pid=old['eestore_pid']).update(**new)


def refetch_entries(force=False, last_fetched=None, verbose=False, OutFile=None, InFile=None):
    source = get_source(_sourcestring)
    if not (force or last_fetched):
        last = source.records.order_by('-last_fetched').first()
        last_fetched = last.last_fetched
    all_entries = []
    if OutFile:
        store_pages(OutFile, last_fetched, verbose)
        return
    if InFile:
        all_entries = utils.load_entries(InFile, last_fetched)
    else:
        for entries in get_pages(last_fetched, verbose=verbose):
            all_entries.extend(entries)
            del entries
    if not last_fetched:
        utils.create_entries(source, all_entries)
    else:
        update_entries(source, all_entries)
