from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django import forms
from django.http.response import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, path

from easydmp.dmpt.models import Section
from easydmp.lib.admin import LockedFilter
from easydmp.lib.admin import PublishedFilter
from easydmp.lib.admin import ImportedFilter
from easydmp.lib.admin import AdminConvenienceMixin
from easydmp.rdadcs.models import RDADCSImportMetadata

from .forms import PlanImportForm
from .import_plan import PlanExportType, PlanImporter
from .models import AnswerSet
from .models import Plan
from .models import PlanAccess
from .models import PlanImportMetadata


class AnswerSetSectionFilter(admin.SimpleListFilter):
    title = 'section'
    parameter_name = 'section'

    def lookups(self, request, _model_admin):
        sections = Section.objects.all()
        key = 'section__template__id__exact'
        template_id = request.GET.get(key, None)
        if template_id:
            sections = sections.filter(template_id=template_id)
        lookups = []
        for section in sections:
            lookups.append((section.pk, str(section)))
        return lookups

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(section__id=self.value())
        return queryset


@admin.register(AnswerSet)
class AnswerSetAdmin(AdminConvenienceMixin, admin.ModelAdmin):
    list_display = ['plan', 'section', 'identifier']
    list_filter = [
        'section__template',
        AnswerSetSectionFilter,
        'skipped',
    ]
    search_fields = ['plan__pk', 'plan__title', 'section__template__title']
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
            if sib:
                url = self.get_change_url(sib.pk)
                return HttpResponseRedirect(url)
        return redirect

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['plan', 'section', 'parent']
        return self.readonly_fields


class PlanExportForm(forms.Form):
    format = forms.ChoiceField(
        choices=PlanExportType.choices,
        widget=forms.RadioSelect,
    )


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


class RDADCSImportMetadataInline(admin.TabularInline):
    model = RDADCSImportMetadata
    fk_name = 'plan'
    fields = ['original_id', 'original_id_type', 'originally_created', 'originally_modified', 'imported', 'imported_via']
    read_only_fields = fields
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Plan)
class PlanAdmin(AdminConvenienceMixin, admin.ModelAdmin):
    list_display = ['title', 'version', 'template', 'added_by', 'added']
    list_filter = [
        'template',
        LockedFilter,
        PublishedFilter,
        ImportedFilter,
    ]
    search_fields = ['id', 'title', 'abbreviation', 'added_by__email', 'added_by__username']
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
        RDADCSImportMetadataInline,
    ]

    # displays

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
                importer = PlanImporter(request, via='admin')
                pim = importer.import_plan()
                importer.message()
                if not pim:
                    return HttpResponseRedirect(
                        reverse(self.get_viewname('import'))
                    )
                importer.audit_log()
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

    # extra buttons on changeform

    def export_plan(self, request, object_id):
        object_id = int(object_id)
        # authorization
        user = request.user
        if not user.has_superpowers:
            raise PermissionDenied

        if request.method == 'POST':
            form = PlanExportForm(request.POST)
            if form.is_valid():
                format = form.cleaned_data['format']
                if format == PlanExportType.EASYDMP:
                    url = reverse('v2:plan-export', kwargs={'pk': object_id})
                    return HttpResponseRedirect(f'{url}?format=json')
                elif format == PlanExportType.RDADCS:
                    url = reverse('v2:plan-export-rda', kwargs={'pk': object_id})
                    return HttpResponseRedirect(url)
                raise ValueError(f'Unsupported format: {format}')
        else:
            form = PlanExportForm()

        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})
        context = {
            'title': 'Export plan',
            'adminForm': adminForm,
            'form': form,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }
        return TemplateResponse(request, 'admin/plan/plan/export_form.html', context)

    # extra urls

    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path('<int:object_id>/export/', self.admin_site.admin_view(self.export_plan),
                name='plan_plan_export'),
            path('import/', self.admin_site.admin_view(self.import_plan),
                name='plan_plan_import'),
        ]
        return extra_urls + urls


@admin.register(PlanAccess)
class PlanAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'may_edit']
    list_filter = ['may_edit']
    search_fields = ['plan__title', 'plan__abbreviation', 'user__username']
    raw_id_fields = ['user', 'plan']
