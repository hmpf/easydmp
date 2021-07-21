from django.contrib import admin
from django.urls import reverse

from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user

from easydmp.auth.utils import set_user_object_permissions
from easydmp.lib import get_model_name


__all__ = [
    'FakeBooleanFilter',
    'PublishedFilter',
    'RetiredFilter',
    'AdminConvenienceMixin',
    'ObjectPermissionModelAdmin',
    'SetObjectPermissionModelAdmin',
]


class FakeBooleanFilter(admin.SimpleListFilter):

    def lookups(self, request, _model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        lookup = '{}__isnull'.format(self.parameter_name)
        if self.value() == 'yes':
            return queryset.filter(**{lookup: False})
        if self.value() == 'no':
            return queryset.filter(**{lookup: True})


class PublishedFilter(FakeBooleanFilter):
    title = 'public'
    parameter_name = 'published'


class RetiredFilter(FakeBooleanFilter):
    title = 'retired'
    parameter_name = 'retired'


class LockedFilter(FakeBooleanFilter):
    title = 'locked'
    parameter_name = 'locked'


class AdminConvenienceMixin:
    def get_viewname(self, viewname):
        admin = self.admin_site.name
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        viewname = viewname
        return f'{admin}:{app_label}_{model_name}_{viewname}'

    def get_change_url(self, pk):
        viewname = self.get_viewname('change')
        return reverse(viewname, args=[pk])


class ObjectPermissionModelAdmin(GuardedModelAdmin):

    def get_queryset(self, request):
        """Limit queryset only to objects with change permission.

        If the optional method ``get_limited_queryset()`` is defined, return
        the set of this and the previous queryset.
        """
        qs = super().get_queryset(request)
        if request.user.has_superpowers:
            return qs

        # Run an explicit filter for the queryset, if any
        limit_qs = qs.none()
        if hasattr(self, 'get_limited_queryset'):
            limit_qs = self.get_limited_queryset(request) & qs

        # Get objects with 'change_<model_name>' object permission
        perm_qs = qs.none()
        if getattr(self, 'has_object_permissions', False):  # Avoid a db call
            model_name = get_model_name(self.model)
            app_label = self.model._meta.app_label
            view_permission = f'{app_label}.view_{model_name}'
            change_permission = f'{app_label}.change_{model_name}'
            perm_qs = get_objects_for_user(
                request.user,
                [view_permission, change_permission],
                klass=qs,
                any_perm=True,
                accept_global_perms=False,
            )

        qs = perm_qs | limit_qs

        return qs.distinct()


class SetObjectPermissionModelAdmin(ObjectPermissionModelAdmin):

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            extra_permissions = getattr(self, 'set_permissions', [])
            set_user_object_permissions(request.user, obj, extra_permissions)
