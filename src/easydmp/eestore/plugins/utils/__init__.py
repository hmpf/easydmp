from datetime import datetime
import json
import sys
import requests

from easydmp.eestore.models import EEStoreType, EEStoreSource, EEStoreCache


__all__ = [
    'convert_page',
    'convert_to_ndjson',
    'get_source',
    'load_entries',
    'parse_datetime',
    'store_entries',
    'wash_entries',
]


def parse_datetime(datestring):
    if datestring.endswith('Z'):
        datestring = datestring[:-1] + '+00:00'
    return datetime.fromisoformat(datestring)


def get_source(sourcestring):
    t, s = sourcestring.split(':')
    type_, _ = EEStoreType.objects.get_or_create(name=t)
    source, _ = EEStoreSource.objects.get_or_create(
        eestore_type=type_,
        name=s,
    )
    return source


def convert_page(raw_entries, extract_entry, last_fetched=None):
    entries = []
    for raw_entry in raw_entries:
        entry = extract_entry(raw_entry, last_fetched)
        if not entry:  # Page too old
            break
        entries.append(entry)
    return entries, len(raw_entries) > len(entries)


def convert_to_ndjson(entries):
    rows = []
    for entry in entries:
        rows.append(json.dumps(entry, separators=(',', ':')))
    return rows


def store_entries(entries, File):
    """Dump entries to ``File``

    It will eventually contain a newline-delimited json stream.

    The ``File`` must be appendable. As the function may be called once per
    page, it cannot be closed herre but must be closed by the caller.
    """
    ndjson = convert_to_ndjson(entries)
    File.dump(ndjson)


def load_entries(File):
    "``File`` contains a newline-delimited json stream"
    try:
        entries = []
        for entrystr in File.readlines():
            entrystr = entrystr.strip()
            entry = json.loads(entrystr)
            entries.append(entry)
        return entries
    finally:
        File.close()


def wash_entries(entries):
    """Remove duplicate records, assumes there's a PID

    First copy found wins"""

    ids_seen = set()
    washed_entries = []
    duplicates = []
    for entry in entries:
        if entry['pid'] in ids_seen:
            duplicates.append(entry)
            continue
        ids_seen.add(entry['pid'])
        washed_entries.append(entry)
    return washed_entries, duplicates


def create_entries(source, entries, start=1, wash=False, verbose=False):
    duplicates = []
    if wash:
        entries, duplicates = wash_entries(entries)
    if duplicates and verbose:
        sys.stderr.write(str(duplicates)+'\n')
    new_entries = []
    for i, entry in enumerate(entries, start=start):
        entry['eestore_id'] = i
        entry['eestore_type'] = source.eestore_type
        entry['source'] = source
        entry['last_fetched'] = parse_datetime(entry['last_fetched'])
        new_entries.append(entry)
    del entries
    objs = [EEStoreCache(**entry) for entry in new_entries]
    EEStoreCache.objects.bulk_create(objs, batch_size=500)


def update_entries(source, entries):
    new_id_map = {e['pid']: e for e in entries}
    del entries
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
        create_entries(new_entries, start=latest.eestore_id+1, wash=True)
    for old, new in changed_entries:
        new['last_fetched'] = parse_datetime(new['last_fetched'])
        EEStoreCache.objects.filter(eestore_pid=old['eestore_pid']).update(**new)
