import warnings

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django import forms
from django.http.response import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, path
from django.utils.html import format_html, mark_safe

from easydmp.eventlog.utils import log_event
from easydmp.lib.admin import LockedFilter
from easydmp.lib.admin import PublishedFilter
from easydmp.lib.admin import ImportedFilter
from easydmp.lib.admin import AdminConvenienceMixin

from .import_plan import deserialize_plan_export, import_serialized_plan_export, PlanImportError
from .models import AnswerSet
from .models import Plan
from .models import PlanAccess
from .models import PlanImportMetadata


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


class PlanImportForm(forms.Form):
    plan_export_file = forms.FileField()


class PlanImportMetadataInline(admin.TabularInline):
    model = PlanImportMetadata
    fk_name = 'plan'
    fields = ['origin', 'original_plan_pk', 'original_template_pk', 'originally_published', 'imported', 'imported_via']
    read_only_fields = fields
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Plan)
class PlanAdmin(AdminConvenienceMixin, admin.ModelAdmin):
    list_display = ['title', 'version', 'template', 'added_by', 'added', 'export']
    list_filter = [
        'template',
        LockedFilter,
        PublishedFilter,
        ImportedFilter,
    ]
    search_fields = ['title', 'abbreviation', 'added_by__email', 'added_by__username']
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
    inlines = [
        PlanImportMetadataInline,
    ]

    # displays

    def export(self, obj):
        json_url = reverse('v2:plan-export', kwargs={'pk': obj.pk})
        html = '<a target="_blank" href="{}?format=json">JSON</a>'
        return format_html(html, mark_safe(json_url))
    export.short_description = 'Export'  # type: ignore
    export.allow_tags = True  # type: ignore

    # actions

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

    # extra buttons on changelist

    def import_plan(self, request):
        # authorization
        user = request.user
        if not (user.has_superpowers or user.has_perm('plan.add_plan')):
            raise PermissionDenied

        # code
        request.current_app = self.admin_site.name
        if request.method == 'POST':
            form = PlanImportForm(request.POST, request.FILES)
            if form.is_valid():
                plan_export_file = request.FILES['plan_export_file']
                plan_export_jsonblob = plan_export_file.read()
                url_on_error = reverse(self.get_viewname('import'))
                try:
                    serialized_dict = deserialize_plan_export(plan_export_jsonblob)
                except PlanImportError as e:
                    error_msg = f'{e}, cannot import'
                    messages.error(request, error_msg)
                    return HttpResponseRedirect(url_on_error)

                try:
                    with warnings.catch_warnings(record=True) as w:
                        pim = import_serialized_plan_export(serialized_dict, request.user, via='admin')
                        if w:
                            messages.warning(request, w[-1].message)
                except PlanImportError as e:
                    messages.error(request, str(e))
                    return HttpResponseRedirect(url_on_error)
                msg = f'Plan "{pim.plan}" successfully imported.'
                messages.success(request, msg)
                log_event(request.user, 'import', target=pim.plan,
                          timestamp=pim.imported,
                          template=msg[:-1])
                # for admin.LogEntry
                self.log_change(request, pim.plan, {'added': {}})
                return HttpResponseRedirect(
                    reverse(self.get_viewname('changelist'))
                )
        else:
            form = PlanImportForm()

        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})
        context = {
            'title': 'Import plan',
            'adminForm': adminForm,
            'form': form,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }
        return TemplateResponse(request, 'admin/plan/plan/import_form.html', context)

    # extra urls

    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path('import/', self.admin_site.admin_view(self.import_plan),
                name='plan_plan_import')
        ]
        return extra_urls + urls


@admin.register(PlanAccess)
class PlanAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'may_edit']
    list_filter = ['may_edit']
    search_fields = ['plan__title', 'plan__abbreviation', 'user__username']
