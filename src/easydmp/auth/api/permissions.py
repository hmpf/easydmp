from rest_framework import permissions


__all__ = [
    'IsActive',
    'IsAuthenticatedAndActive',
]


class IsActive(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.is_active

IsAuthenticatedAndActive = permissions.IsAuthenticated & IsActive
