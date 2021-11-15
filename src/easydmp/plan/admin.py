from django.contrib import admin
from django.http.response import HttpResponseRedirect

from easydmp.lib.admin import FakeBooleanFilter
from easydmp.lib.admin import LockedFilter
from easydmp.lib.admin import PublishedFilter
from easydmp.lib.admin import AdminConvenienceMixin

from .models import AnswerSet
from .models import Plan
from .models import PlanAccess


@admin.register(AnswerSet)
class AnswerSetAdmin(AdminConvenienceMixin, admin.ModelAdmin):
    list_display = ['plan', 'section', 'identifier']
    list_filter = ['section__template', 'section', 'skipped']
    search_fields = ['plan__title', 'section__template__title']
    readonly_fields = ['valid', 'last_validated', 'cloned_from', 'cloned_when']
    raw_id_fields = ['plan', 'section', 'parent']
    fieldsets = (
        (None, {
            'fields': ('identifier', 'parent', 'section', 'plan', 'skipped'),
        }),
        ('Debug', {
            'fields': ('data', 'previous_data'),
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': (('valid', 'last_validated'), ('cloned_from', 'cloned_when'),),
        }),
    )
    change_form_template = "easydmp/plan/admin/answerset_changeform.html"

    def response_change(self, request, obj):
        redirect = super().response_change(request, obj)
        if "_add-sibling" in request.POST:
            sib = obj.add_sibling()
            url = self.get_change_url(sib.pk)
            return HttpResponseRedirect(url)
        return redirect

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['plan', 'section', 'parent']
        return self.readonly_fields


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'version', 'template', 'added_by', 'added']
    list_filter = ['template', LockedFilter, PublishedFilter]
    search_fields = ['title', 'abbreviation', 'added_by__email', 'added_by__username',]
    readonly_fields = ['added', 'added_by', 'uuid', 'locked', 'locked_by',
                       'cloned_from', 'cloned_when',
                       'published', 'published_by', 'generated_html']
    actions = ['lock', 'publish']
    date_hierarchy = 'added'
    fieldsets = (
        (None, {
            'fields': ('title', 'abbreviation', 'version', 'template',),
        }),
        ('Debug', {
            'classes': ('collapse',),
            'fields': ('visited_sections',),
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('uuid', ('added', 'added_by'), ('locked', 'locked_by'), ('cloned_from', 'cloned_when'),),
        }),
        ('Post-published metadata', {
            'classes': ('collapse',),
            'fields': ('doi', ('published', 'published_by'), 'generated_html',),
        }),
    )

    def lock(self, request, queryset):
        for q in queryset.filter(locked__isnull=True):
            q.lock(request.user)
            self.message_user(request, 'Successfully locked "{}"'.format(str(q)))
    lock.short_description = 'Lock (set read-only) plans'  # type: ignore

    def publish(self, request, queryset):
        for q in queryset.filter(locked__isnull=True, published__isnull=True):
            q.publish(request.user)
            self.message_user(request, 'Successfully published "{}"'.format(str(q)))
    publish.short_description = 'Publish plans'  # type: ignore


@admin.register(PlanAccess)
class PlanAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'may_edit']
    list_filter = ['may_edit']
    search_fields = ['plan__title', 'plan__abbreviation', 'user__username']
