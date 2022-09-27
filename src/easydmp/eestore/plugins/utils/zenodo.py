import requests


__all__ = []


def get_resource(endpoint, params=None):
    if not params:
        params = {}
    r = requests.get(endpoint, params=params)
    if r.status_code != requests.codes.ok:
        return None
    jsonblob = r.json()
    return jsonblob
