from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.viewsets import ReadOnlyModelViewSet


__all__ = ['AnonReadOnlyModelViewSet']


class AnonReadOnlyModelViewSet(ReadOnlyModelViewSet):
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]
