from django.contrib import admin

from .models import Plan, PlanComment


class FakeBooleanFilter(admin.SimpleListFilter):

    def lookups(self, request, model_admin):
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


class LockedFilter(FakeBooleanFilter):
    title = 'Locked'
    parameter_name = 'locked'


class PublishedFilter(FakeBooleanFilter):
    title = 'Published'
    parameter_name = 'published'


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'added_by', 'added']
    list_filter = ['template', LockedFilter, PublishedFilter]
    readonly_fields = ['added', 'added_by', 'uuid', 'locked', 'locked_by', 'published', 'published_by']
    actions = ['lock', 'publish']

    def lock(self, request, queryset):
        for q in queryset.filter(locked__isnull=True):
            q.lock(request.user)
            self.message_user(request, 'Successfully locked "{}"'.format(str(q)))
    lock.short_description = 'Lock (set read-only) plans'

    def publish(self, request, queryset):
        for q in queryset.filter(locked__isnull=True, published__isnull=True):
            q.publish(request.user)
            self.message_user(request, 'Successfully published "{}"'.format(str(q)))
    publish.short_description = 'Publish plans'


@admin.register(PlanComment)
class PlanCommentAdmin(admin.ModelAdmin):
    list_display = ['plan', 'question', 'added_by', 'added']
    list_filter = ['plan']
    search_fields = ['plan__title', 'added_by__email', 'added_by__username',
                     'question__question', 'question__label']
