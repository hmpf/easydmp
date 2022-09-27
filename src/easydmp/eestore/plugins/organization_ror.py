from datetime import datetime, timezone
import json
import sys

import requests

from easydmp.eestore.models import EEStoreType, EEStoreSource, EEStoreCache
from easydmp.esestore.plugins.utils import get_source
from easydmp.esestore.plugins.utils import zenodo
from easydmp.esestore.plugins import utils


__all__ = [
    'refetch_entries',
]


TYPE = 'organization'
SOURCE = 'ror'
ENDPOINT = 'https://zenodo.org/api/records/?communities=ror-data&sort=mostrecent'
_sourcestring = f'{TYPE}:{SOURCE}'


def get_packed_dataset(last_fetched=None, verbose=False):
    queryparams = {
        'communities': 'ror-data',
        'sort': 'mostrecent',
    }
    jsonblob = zenodo.get_resource(ENDPOINT, queryparams)
    resource = jsonblob['hits']['hits'][0]['files'][-1]
    filename = resource['key']

    if last_fetched:
        version, year, month, day, *_ = filename.split('-')
        released = datetime(year, month, day, 0, 0, 0, 0, timezone.utc)
        if last_fetched >= released:
            return None

    download_link = resource['links']['self']

    # download file
    # unpack file safely
    # parse dataset
    # return entries


def extract_entry(jsonblob, last_fetched=None):
    remote_id = jsonblob['id']
    links = jsonblob.get('links', [])
    uri = links[0] if links else ''
    acronyms = jsonblob.get('acronyms', [])
    acronym = acronyms[0] if acronyms else ''
    entry = {
        'eestore_pid': f'{TYPE}:{SOURCE}:{remote_id}',
        'name': jsonblob['name'],
        'pid': remote_id,
        'remote_id': remote_id,
        'uri': uri,
        'last_fetched': None,
        'data': {
            'acronym': acronym,
        }
    }
    return entry


def refetch_entries(force=False, last_fetched=None, verbose=False, OutFile=None, InFile=None):
    source = get_source()
    if not (force or last_fetched):
        last = source.records.order_by('-last_fetched').first()
        last_fetched = last.last_fetched
    all_entries = []
    if OutFile:
        utils.store_entries(OutFile, last_fetched, verbose)
        return
    if InFile:
        all_entries = utils.load_entries(InFile, last_fetched)
    else:
        for entries in get_packed_dataset(last_fetched, verbose=verbose):
            all_entries.extend(entries)
            del entries
    if not last_fetched:
        utils.create_entries(all_entries, verbose=verbose)
    else:
        utils.update_entries(all_entries)
