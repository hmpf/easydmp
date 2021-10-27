from rest_framework import permissions


__all__ = [
    'IsActive',
    'HasSuperpowers',
    'IsAuthenticatedAndActive',
]


class IsActive(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.is_active


class HasSuperpowers(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user.has_superpowers


IsAuthenticatedAndActive = permissions.IsAuthenticated & IsActive
