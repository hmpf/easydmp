from collections import OrderedDict

from rest_framework import pagination
from rest_framework.response import Response


__all__ = [
    'PageNumberPagination',
    'ToggleablePageNumberPaginationV1',
    'ToggleablePageNumberPaginationV2',
]


class PageNumberPagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'


class ToggleablePageNumberPaginationV1(PageNumberPagination):
    """Paginate if `page_size` is an integer in GET query parameters

    Pagination is by default off.

    Valid values to get-parameter: any positive integer
    """

    def paginate_queryset(self, queryset, request, view=None):
        page_size = 0
        try:
            page_size = int(request.query_params.get(self.page_size_query_param, 0))
        except TypeError:
            pass
        if page_size:  # Reuse page_size to enable pagination
            return super().paginate_queryset(queryset, request, view)
        return None


class ToggleablePageNumberPaginationV2(PageNumberPagination):
    """Paginate with `page_size` via GET query parameter or from settings

    Whether pagination is on by default is controlled via settings, settings
    can be overruled by having page_size in a GET parameter. "0" means turn
    pagination off.

    Valid values to get-parameter:
    * 0: turn pagination off
    * any positive integer: entries per page
    * max: if max_page_size is set in settings, paginate with that
    """

    def get_page_size(self, request):
        query_page_size = request.query_params.get(self.page_size_query_param, self.page_size)
        if not query_page_size:
            return None
        if query_page_size == 'max':
            return self.max_page_size or self.page_size or None
        try:
            page_size = max(int(query_page_size), 0)
        except (ValueError, TypeError):
            return None
        if self.max_page_size:
            return min(self.max_page_size, page_size)
        return page_size

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('on_page', len(self.page.object_list)),
            ('page_size', self.page.paginator.per_page),
            ('max_page_size', self.max_page_size or None),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_paginated_response_schema(self, schema):
        pagination_response_schema = super().get_paginated_response_schema(schema)
        return {
            'type': pagination_response_schema['type'],
            'properties': {
                'count': pagination_response_schema['properties']['count'],
                'on_page': {
                    'type': 'integer',
                    'example': 100,
                },
                'page_size': {
                    'type': 'integer',
                    'example': 100,
                    'nullable': True,
                },
                'max_page_size': {
                    'type': 'integer',
                    'example': 1000,
                    'nullable': True,
                },
                'next': pagination_response_schema['properties']['next'],
                'previous': pagination_response_schema['properties']['previous'],
                'results': schema,
            }
        }
