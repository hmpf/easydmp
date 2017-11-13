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
        self.api_root = endpoint_api_root
        self.endpoints = self.get_endpoints()
        print('Endpoints', self.endpoints)

    def get_endpoints(self):
        r = rawget(self.api_root)
        data = r.json()
        endpoints = data['data']
        return endpoints

    def get_repo_endpoint(self, repotype):
        print('Repotype', repotype)
        endpoint = self.endpoints.get(repotype, None)
        print('Endpoints', self.endpoints, endpoint)
        if not repotype in self.endpoints:
            assert False, 'WUT'
        if endpoint is None:
            raise ClientException('Repo "{}" is not supported by the eestore at "{}"'.format(repotype, self.api_root))
        return endpoint

    def available_repos(self):
        return self.endpoints.keys()

    def get_repo(self, repotype):
        return EEStoreRepo(self, repotype)


class EEStoreRepo:

    def __init__(self, server, repotype):
        self.repotype = repotype
        self.server = server
        self.endpoint = self.server.get_repo_endpoint(repotype)
        print(self.endpoint)

    @staticmethod
    def get_pagination_status(data):
        return data['meta']['pagination']

    @staticmethod
    def get_pagination_links(data):
        return data['links']

    def get_list_page(self, link=None, verbose=False, debug=False, **params):
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
            raise ClientException('None found in {}'.format(self.repotype))
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
