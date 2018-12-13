"""Vendored client to access EEStore"""

import sys

import requests


class ClientException(Exception):
    pass


def rawget(endpoint, verbose=False, debug=False, **params):
    if verbose:
        print('Will try to GET:', endpoint)
    r = requests.get(endpoint, params=params)
    if not r.status_code == 200:
        raise ClientException('Endpoint "{}" does not answer correctly'.format(endpoint))
    return r


class EEStoreServer:

    def __init__(self, endpoint_api_root):
        "Uses the source-type endpoint to fetch source endpoints"
        self.api_root = endpoint_api_root
        self.sourcetypes = self.fetch_sourcetypes()
        self._repotypes = set(self.sourcetypes.keys())

    @classmethod
    def get_json(cls, endpoint):
        r = rawget(endpoint)
        return r.json()

    def _check_repotype(self, repotype):
        if not repotype in self._repotypes:
            raise ClientException('Repotype "{}" not known'.format(repotype))

    def fetch_sources(self, item):
        endpoint = item['relationships']['sources']['links']['related']
        data = self.get_json(endpoint)
        sources = {}
        for source in data['data']:
            if source['type'] != 'Source':
                continue
            name = source['attributes']['name']
            endpoint = source['attributes']['endpoint']
            sources[name] = endpoint
        return sources

    def fetch_sourcetypes(self):
        data = self.get_json(self.api_root)
        sourcetypes = {}
        for item in data['data']:
            name = item['attributes']['name']
            sourcetypes[name] = {
                'endpoint': item['attributes']['endpoint'],
                'sources': self.fetch_sources(item),
            }
        return sourcetypes

    def get_sourcetype_endpoint(self, repotype):
        self._check_repotype(repotype)
        repo = self.sourcetypes.get(repotype, None)
        if repo is None:
            raise ClientException('Repo "{}" is not supported by the eestore at "{}"'.format(repotype, self.api_root))
        return repo['endpoint']

    @property
    def available_repos(self):
        return self._repotypes

    def get_repo(self, repotype):
        self._check_repotype(repotype)
        return EEStoreRepo(self, repotype)


class EEStoreRepo:

    def __init__(self, server, repotype, verbose=False):
        self.repotype = repotype
        self.server = server
        self.endpoint = self.server.get_sourcetype_endpoint(repotype)
        self.verbose = verbose
        if verbose:
            print(self.endpoint)

    @staticmethod
    def get_pagination_status(data):
        return data['meta']['pagination']

    @staticmethod
    def get_pagination_links(data):
        return data['links']

    def get_list_page(self, link=None, verbose=False, debug=False, **params):
        verbose = verbose or self.verbose
        if not link:
            link = self.endpoint
        r = rawget(link, verbose=verbose, debug=debug, **params)
        data = r.json()
        page_status = self.get_pagination_status(data)
        links = self.get_pagination_links(data)
        if debug:
            print('Kwargs:', params, file=sys.stderr)
            print('Page status:', page_status, file=sys.stderr)
            print('Links:', links, file=sys.stderr)
            #print('Data:', data['data'], file=sys.stderr)
        return data['data'], page_status, links

    def get_list(self, source=None, search=None, verbose=False, debug=False):
        verbose = verbose or self.verbose
        params = {}
        if source:
            params['source'] = source
        if search:
            params['search'] = search
        if debug:
            print('Source:', source)
            print('Search:', search)
            print('Kwargs, first page:', params)
        repo_list, page_status, links = self.get_list_page(link=None, verbose=verbose, debug=debug, **params)
        if page_status['count'] == 0:
            if verbose:
                print('None found for {}'.format(self.repotype))
            yield from ()
        if page_status['pages'] == 1:
            if verbose:
                print('Single page')
            # Single page
            yield from repo_list
        else:
            params.pop('source', None)
            params.pop('search', None)
            if verbose:
                print('Multi page')
            while links['next'] is not None:
                if debug:
                    print('Kwargs, later pages:', params)
                next_repo_list, _, links = self.get_list_page(link=links['next'], verbose=verbose, debug=debug, **params)
                if verbose:
                    print('Next page:')
                yield from next_repo_list


def get_repo_list(repotype, server, source=None, search=None, verbose=False, debug=False):
    repo = server.get_repo(repotype)
    return repo.get_list(source=source, search=search, verbose=False, debug=False)
