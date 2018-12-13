from django.conf import settings

from .client import EEStoreServer

EESTORE_API_ROOT = 'https://eestore.paas2.uninett.no/api/source-types/'


def get_types_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    assert server or endpoint, 'Either `server` or `endpoint` must be given'
    server = server or EEStoreServer(endpoint)
    return {st: data['endpoint'] for st, data in server.sourcetypes.items()}


def get_sources_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    assert server or endpoint, 'Either `server` or `endpoint` must be given'
    server = server or EEStoreServer(endpoint)
    return server.sourcetypes


def get_entries_from_eestore(server=None, endpoint=EESTORE_API_ROOT):
    assert server or endpoint, 'Either `server` or `endpoint` must be given'
    server = server or EEStoreServer(endpoint)
    for reponame, data in get_sources_from_eestore(server).items():
        repo = server.get_repo(reponame)
        yield from repo.get_list()


def parse_single_row(item):
    data = item['attributes'].copy()
    text_eestore_type = item['type'].lower()
    text_source = data.pop('source')
    eestore_pid = data.pop('pid')

    return {
        'source': text_source,
        'eestore_pid': eestore_pid,
        'eestore_id': item['id'],
        'eestore_type': text_eestore_type,
        'eestore_pid': eestore_pid,
        'last_fetched': data.pop('last_fetched'),
        'name': data.pop('name'),
        'uri': data.pop('uri'),
        'remote_id': data.pop('remote_id'),
        'pid': data.pop('remote_pid'),
        'data': data,
    }
