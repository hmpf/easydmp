from rest_framework import pagination


__all__ = [
    'PageNumberPagination',
    'ToggleablePageNumberPagination',
]


class PageNumberPagination(pagination.PageNumberPagination):
    page_size_query_param = 'page_size'


class ToggleablePageNumberPagination(PageNumberPagination):
    "Paginate if `page_size` is an integer in GET query paramaters"

    def paginate_queryset(self, queryset, request, view=None):
        page_size = 0
        try:
            page_size = int(request.query_params.get(self.page_size_query_param, 0))
        except TypeError:
            pass
        if page_size:  # Reuse page_size to enable pagination
            return super().paginate_queryset(queryset, request, view)
        return None
