# -*- coding: utf-8 -*-
import warnings

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django import forms
from django.template.response import TemplateResponse
from django.http.response import HttpResponseRedirect
from django.urls import reverse, path
from django.utils.html import format_html, mark_safe

from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user, assign_perm

from easydmp.auth.utils import set_user_object_permissions
from easydmp.eestore.models import EEStoreMount
from easydmp.eventlog.utils import log_event
from easydmp.lib.admin import FakeBooleanFilter
from easydmp.lib.admin import PublishedFilter
from easydmp.lib.admin import RetiredFilter
from easydmp.lib.admin import LockedFilter
from easydmp.lib.admin import ObjectPermissionModelAdmin
from easydmp.lib.admin import SetObjectPermissionModelAdmin
from easydmp.lib import get_model_name

from .import_template import deserialize_template_export, import_serialized_export, TemplateImportError
from .models import Template
from .models import TemplateImportMetadata
from .models import Section
from .models import ExplicitBranch
from .models import Question
from .models import CannedAnswer
from .positioning import Move

"""
The admin is simplified for non-superusers. Branching sections are disallowed,
hence all questions are on_trunk.
"""


def get_templates_for_user(user):
    templates = get_objects_for_user(
        user,
        'dmpt.change_template',
        accept_global_perms=False,
    )
    return templates


def get_sections_for_user(user):
    templates = get_templates_for_user(user)
    return Section.objects.filter(template__in=templates)


def get_questions_for_user(user):
    sections = get_sections_for_user(user)
    return Question.objects.filter(section__in=sections)


def get_canned_answers_for_user(user):
    questions = get_questions_for_user(user)
    return CannedAnswer.objects.filter(question__in=questions)


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


class BaseOrderingInline(admin.TabularInline):
    """
    The following attributes must be set on subclasses:

    * model: the model that is ordered
    * fk_name: the foreign key on the model that points to the parent
    * movement_view: the name of the view that reorders the queryset
    * verbose_name_plural: should be something like "MODELNAME ordering", to
      separate it from any other subclasses of InlineModelAdmin

    The following methods must be set on subclasses:

    * get_order: a method that calls a method on the parent to get the current
      order of objects. It takes an instance of ``parent`` as its sole argument.

    You may override:

    * ordering_fieldname: the field that holds the order, by default "position"
    * item: a method that prints a human readable summary of the object to be
      ordered, by default ``str(obj)``

    If you extend an BaseOrderingInline to work as a normal inline, you should
    probably also override the following:

    * readonly_fields: ordering_fieldname needs to be in here if it is in fields
    * fields: must contain "movement", for the movement buttons
    * extra
    * can_delete
    * show_change_link
    * has_add_permission: in a normal BaseOrderingInline this is always False
    """
    ordering_fieldname: str = 'position'
    ordering = [ordering_fieldname]
    fields = ('movement', ordering_fieldname, 'item')
    extra = 0
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def get_order(self, parent):
        raise NotImplementedError

    def item(self, obj):
        return str(obj)

    def get_parent(self, obj):
        return getattr(obj, self.fk_name)

    def _get_button_link(self, obj, movement):
        opts = self.model._meta
        parent = self.get_parent(obj)
        kwargs = {'parent_pk': parent.pk, 'pk': obj.pk, 'movement': movement.value}
        return reverse(
            self.movement_view_pattern % (self.admin_site.name, opts.app_label),
            kwargs=kwargs
        )

    def has_add_permission(self, request, _=None):
        return False

    @mark_safe
    def movement(self, obj):
        buttons = {
            Move.UP: {'active': True, 'icon': '⭡'},
            Move.TOP: {'active': True, 'icon': '⭱'},
            Move.DOWN: {'active': True, 'icon': '⭣'},
            Move.BOTTOM: {'active': True, 'icon': '⭳'},
        }
        parent = self.get_parent(obj)
        order = self.get_order(parent)
        obj_index = order.index(obj.pk)
        # Deactivate invalid movement directions
        if obj_index == 0:
            buttons[Move.UP]['active'] = False
            buttons[Move.TOP]['active'] = False
        if obj_index == len(order) - 1:
            buttons[Move.DOWN]['active'] = False
            buttons[Move.BOTTOM]['active'] = False
        # Build html, this should maybe be a template or widget
        button_html = []
        icon_html_template = '<span class="{button}">{icon}</span>'
        for button, data in buttons.items():
            icon = data['icon']
            icon_html = icon_html_template.format(button=button, icon=icon)
            if data['active']:
                link = self._get_button_link(obj, button)
                html = f'<a href="{link}" title="{button}"><button type="button" class="button move">' + icon_html + '</button></a>'
            else:
                html = f'<button type="button" class="button move" disabled>{icon}</button>'
            button_html.append(html)
        return ' '.join(button_html)


class TemplateAuthMixin:
    message_cannot_delete = ('The {} cannot be deleted because it is'
                             ' in use by one or more plans.')

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_readonly:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_readonly:
            if obj.in_use():
                model = get_model_name(obj)
                self.message_user(
                    request, 
                    self.message_cannot_delete.format(model),
                    level=messages.WARNING
                )
                return False
        return super().has_delete_permission(request, obj)


class TemplateImportForm(forms.Form):
    template_export_file = forms.FileField()


class TemplateDescriptionFilter(admin.SimpleListFilter):
    title = 'has description'
    parameter_name = 'has_description'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            queryset = queryset.exclude(description='')
        elif value == 'no':
            queryset = queryset.filter(description='')
        return queryset


class TemplateMoreInfoFilter(admin.SimpleListFilter):
    title = 'has more info'
    parameter_name = 'has_more_info'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            queryset = queryset.exclude(more_info='')
        elif value == 'no':
            queryset = queryset.filter(more_info='')
        return queryset


class ImportedFilter(admin.SimpleListFilter):
    title = 'imported'
    parameter_name = 'imported'

    def lookups(self, request, model_admin):
        return (('yes', 'Yes'), ('no', 'No'))

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            queryset = queryset.exclude(import_metadata=None)
        elif value == 'no':
            queryset = queryset.filter(import_metadata=None)
        return queryset


class TemplateImportMetadataInline(admin.TabularInline):
    model = TemplateImportMetadata
    fk_name = 'template'
    fields = ['origin', 'original_template_pk', 'originally_cloned_from', 'originally_published', 'imported', 'imported_via']
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class SectionOrderingInline(BaseOrderingInline):
    model = Section
    fk_name = 'template'
    fields = ('movement', 'position', 'section_depth', 'item')
    readonly_fields = fields
    movement_view_pattern = '%s:%s-template-section-reorder'
    verbose_name_plural = "Section ordering"

    def get_order(self, parent):
        return parent.get_section_order()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(super_section=None)

    def item(self, obj):
        return obj.full_title()


@admin.register(Template)
class TemplateAdmin(AdminConvenienceMixin, TemplateAuthMixin, SetObjectPermissionModelAdmin):
    list_display = ('id', 'version', 'title', 'is_locked', 'is_published', 'is_retired', 'is_imported', 'export')
    list_display_links = ('title', 'version', 'id')
    date_hierarchy = 'published'
    set_permissions = ['use_template']
    has_object_permissions = True
    list_filter = [
        LockedFilter,
        PublishedFilter,
        RetiredFilter,
        ImportedFilter,
        'domain_specific',
        TemplateDescriptionFilter,
        TemplateMoreInfoFilter,
    ]
    inlines = [
        SectionOrderingInline,
        TemplateImportMetadataInline,
    ]
    actions = [
        'new_version',
        'private_copy',
    ]
    fieldsets = (
        (None, {
            'fields': ('title', 'abbreviation', 'version', 'description',
                       'more_info', 'reveal_questions', 'domain_specific',
                       'locked', 'published', 'retired'),
        }),
        ('Advanced', {
            'fields': ('cloned_from', 'cloned_when',),
            'classes': ('collapse',),
        }),
    )

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Section reordering supermagic

    def reorder_sections(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        try:
            parent.reorder_sections(pk, movement)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    # extra buttons on changelist

    def import_template(self, request):
        # authorization
        user = request.user
        if not (user.has_superpowers or user.has_perm('dmpt.add_template')):
            raise PermissionDenied

        # code
        request.current_app = self.admin_site.name
        if request.method == 'POST':
            template_export = request.FILES['template_export_file']
            form = TemplateImportForm(request.POST, request.FILES)
            if form.is_valid():
                template_export_file = request.FILES['template_export_file']
                template_export_jsonblob = template_export_file.read()
                url_on_error = reverse(self.get_viewname('import'))
                try:
                    serialized_dict = deserialize_template_export(template_export_jsonblob)
                except TemplateImportError as e:
                    error_msg = f'{e}, cannot import'
                    messages.error(request, error_msg)
                    return HttpResponseRedirect(url_on_error)

                try:
                    with warnings.catch_warnings(record=True) as w:
                        tim = import_serialized_export(serialized_dict, via='admin')
                        if w:
                            messages.warning(request, w[-1].message)
                except TemplateImportError as e:
                    messages.error(request, str(e))
                    return HttpResponseRedirect(url_on_error)
                msg = f'Template "{tim.template}" successfully imported.'
                messages.success(request, msg)
                log_event(request.user, 'import', target=tim.template,
                          timestamp=tim.imported,
                          template=msg[:-1])
                # for admin.LogEntry
                self.log_change(request, tim.template, {'added': {}})
                if not request.user.has_superpowers:
                    extra_permissions = getattr(self, 'set_permissions', [])
                    # TD's may view and use the imported template regardless
                    assign_perm('view_template', request.user, tim.template)
                    for perm in extra_permissions:
                        assign_perm(perm, request.user, tim.template)
                    template = tim.template
                    # TD's may work on a copy of a locked import
                    if template.locked:
                        template = template.private_copy()
                        # for admin.LogEntry
                        self.log_change(request, template, {'added': {}})
                    set_user_object_permissions(request.user, template, extra_permissions)
                return HttpResponseRedirect(
                    reverse(self.get_viewname('changelist'))
                )
        else:
            form = TemplateImportForm()

        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})
        context = {
            'title': 'Import template',
            'adminForm': adminForm,
            'form': form,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }
        return TemplateResponse(request, 'admin/dmpt/template/import_form.html', context)

    # extra urls

    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path('<int:parent_pk>/section/<int:pk>/<str:movement>/',
                 self.admin_site.admin_view(self.reorder_sections),
                 name='dmpt-template-section-reorder'),
            path('import/', self.admin_site.admin_view(self.import_template),
                 name='dmpt_template_import')
        ]
        return extra_urls + urls

    # displays

    def is_locked(self, obj):
        if obj.locked:
            return True
        return False
    is_locked.short_description = 'Is locked'  # type: ignore
    is_locked.boolean = True  # type: ignore

    def is_published(self, obj):
        if obj.published:
            return True
        return False
    is_published.short_description = 'Is published'  # type: ignore
    is_published.boolean = True  # type: ignore

    def is_retired(self, obj):
        if obj.retired:
            return True
        return False
    is_retired.short_description = 'Is retired'  # type: ignore
    is_retired.boolean = True  # type: ignore

    def is_imported(self, obj):
        if obj.import_metadata.exists():
            return True
        return False
    is_imported.short_description = 'Is imported'  # type: ignore
    is_imported.boolean = True  # type: ignore

    def export(self, obj):
        json_url = reverse('v2:template-export', kwargs={'pk': obj.pk})
        html = '<a target="_blank" href="{}">JSON</a>'
        return format_html(html, mark_safe(json_url))
    export.short_description = 'Export'  # type: ignore
    export.allow_tags = True  # type: ignore

    # actions

    def new_version(self, request, queryset):
        for q in queryset.all():
            q.new_version()
    new_version.short_description = 'Create new version'  # type: ignore
    new_version.allowed_permissions = ('add',)  # type: ignore

    def private_copy(self, request, queryset):
        for q in queryset.all():
            q.private_copy()
    private_copy.short_description = 'Make a private copy'  # type: ignore
    private_copy.allowed_permissions = ('add',)  # type: ignore


class SubsectionOrderingInline(BaseOrderingInline):
    model = Section
    fk_name = 'super_section'
    fields = ('movement', 'position', 'section_depth', 'item')
    readonly_fields = fields
    movement_view_pattern = '%s:%s-section-section-reorder'
    verbose_name_plural = "Subsection ordering"

    def get_order(self, parent):
        return parent.get_section_order()

    def item(self, obj):
        return obj.full_title()


class QuestionOrderingInline(BaseOrderingInline):
    model = Question
    fk_name = 'section'
    movement_view_pattern = '%s:%s-section-question-reorder'
    verbose_name_plural = "Question ordering"

    def get_order(self, parent):
        return parent.get_question_order()

    def item(self, obj):
        return str(obj)


@admin.register(Section)
class SectionAdmin(AdminConvenienceMixin, TemplateAuthMixin, ObjectPermissionModelAdmin):
    list_display = (
        'template',
        'position',
        'section_depth',
        'id',
        'title',
        'graph_pdf',
    )
    list_display_links = ('template', 'section_depth', 'id', 'position')
    list_filter = ('branching', 'template', 'optional')
    ordering = ('template', 'position',)
    search_fields = [
        '=id',
        'title',
    ]
    fieldsets = (
        (None, {
            'fields': ('template', 'title', 'position', 'label', 'branching',
                       'optional', 'introductory_text', 'comment'),
        }),
        ('Super section', {
            'fields': ('super_section', 'section_depth'),
        }),
        ('Advanced', {
            'fields': ('cloned_from', 'cloned_when'),
            'classes': ('collapse',),
        }),
    )
    inlines = [SubsectionOrderingInline, QuestionOrderingInline]
    readonly_fields = ['cloned_from', 'cloned_when', 'position']
    _model_slug = 'section'

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Reordering supermagic

    def reorder_sections(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        try:
            parent.reorder_sections(pk, movement)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    def reorder_questions(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        try:
            parent.reorder_questions(pk, movement)
        except ValueError as error:
            self.message_user(str(error), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    # Overrides

    def get_limited_queryset(self, request):
        return get_sections_for_user(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'template' and not request.user.has_superpowers:
            templates = get_templates_for_user(request.user)
            kwargs["queryset"] = templates
        if db_field.name == 'super_section':
            kwargs["queryset"] = self.get_queryset(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            position = obj.get_next_section_position()
            obj.position = position
        super().save_model(request, obj, form, change)

    # extra urls

    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path('<int:parent_pk>/section/<int:pk>/<str:movement>/',
                 self.admin_site.admin_view(self.reorder_sections),
                 name='dmpt-section-section-reorder'),
            path('<int:parent_pk>/question/<int:pk>/<str:movement>/',
                 self.admin_site.admin_view(self.reorder_questions),
                 name='dmpt-section-question-reorder'),
        ]
        return extra_urls + urls

    # display fields

    def graph_pdf(self, obj):
        pdf_url = reverse('v1:section-graph', kwargs={'pk': obj.pk})
        html = '<a target="_blank" href="{}">PDF</a>'
        return format_html(html, mark_safe(pdf_url))
    graph_pdf.short_description = 'Graph'  # type: ignore
    graph_pdf.allow_tags = True  # type: ignore


class QuestionExplicitBranchInline(admin.StackedInline):
    model = ExplicitBranch
    fk_name = "current_question"
    raw_id_fields = ['next_question']

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_superpowers:
            return ()
        return [f.name for f in self.model._meta.fields]


class QuestionCannedAnswerInline(admin.StackedInline):
    model = CannedAnswer
    raw_id_fields = ['transition']
    readonly_fields = ('position', 'cloned_from', 'cloned_when')
    ordering = ['position']

    def save_model(self, request, obj, form, change):
        if not change:
            position = obj.get_next_position()
            obj.position = position
        super().save_model(request, obj, form, change)


class QuestionEEStoreMountInline(admin.StackedInline):
    model = EEStoreMount


class QuestionHasEEStoreFilter(FakeBooleanFilter):
    title = 'has EEStore mount'
    lookup = 'eestore'
    parameter_name = 'eestore'


class QuestionEEStoreTypeFilter(admin.SimpleListFilter):
    title = 'EEStore type'
    parameter_name = 'eestore'

    def lookups(self, request, _model_admin):
        questions = get_questions_for_user(request.user)
        types = (
            EEStoreMount.objects
                 .filter(question__in=questions)
                 .values_list('eestore_type__name', flat=True)
                 .distinct()
        )
        return tuple(zip(*(types, types)))

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(eestore__eestore_type__name=self.value())
        return queryset


class QuestionTemplateFilter(admin.SimpleListFilter):
    title = 'template'
    parameter_name = 'template'

    def lookups(self, request, _model_admin):
        templates = get_templates_for_user(request.user)
        lookups = []
        for template in templates:
            lookups.append((template.pk, str(template)))
        return lookups

    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(section__template__id=self.value())
        return queryset


class QuestionSectionFilter(admin.SimpleListFilter):
    title = 'section'
    parameter_name = 'section'

    def lookups(self, request, _model_admin):
        sections = get_sections_for_user(request.user)
        template_id = request.GET.get('template', None)
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


class QuestionCannedAnswerOrderingInline(BaseOrderingInline):
    model = CannedAnswer
    fk_name = 'question'
    movement_view_pattern = '%s:%s-question-cannedanswer-reorder'
    verbose_name_plural = "Canned answer ordering"

    def get_order(self, parent):
        return parent.get_canned_answer_order()


@admin.register(Question)
class QuestionAdmin(AdminConvenienceMixin, TemplateAuthMixin, ObjectPermissionModelAdmin):
    list_display = (
        'position',
        'id',
        'question',
        'section',
        'input_type',
        'on_trunk',
        'optional',
        'get_mount',
    )
    list_select_related = ['section']
    list_display_links = ('position', 'id', 'question')
    search_fields = [
        '=id',
        'question',
        'section__title',
    ]
    actions = [
        'toggle_on_trunk',
    ]
    list_filter = [
        'on_trunk',
        'optional',
        QuestionTemplateFilter,
        QuestionSectionFilter,
        QuestionHasEEStoreFilter,
        QuestionEEStoreTypeFilter,
    ]
    inlines = [
        QuestionCannedAnswerInline,
        QuestionCannedAnswerOrderingInline,
        QuestionExplicitBranchInline,
        QuestionEEStoreMountInline,
    ]
    save_on_top = True
    fieldsets = (
        (None, {
            'fields': ('input_type', 'section', 'position', 'label',
                       'question', 'on_trunk', 'optional', 'help_text',
                       'framing_text', 'comment',),
        }),
        ('Options for optional questions', {
            'fields': ('optional_canned_text',),
            'classes': ('collapse',),
        }),
        ('Advanced', {
            'fields': ('cloned_from', 'cloned_when',),
            'classes': ('collapse',),
        }),
    )
    _model_slug = 'question'

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Reordering supermagic

    def reorder_canned_answers(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        try:
            parent.reorder_canned_answers(pk, movement)
        except ValueError as error:
            self.message_user(str(error), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    # overrides

    def get_readonly_fields(self, request, obj=None):
        readonly = ('cloned_from', 'cloned_when')
        if request.user.has_superpowers:
            return readonly
        return readonly + ('on_trunk',)

    def get_queryset(self, request):
        return get_questions_for_user(request.user)

    def get_object(self, request, object_id, from_field=None):
        queryset = self.get_queryset(request)
        model = queryset.model
        field = model._meta.pk if from_field is None else model._meta.get_field(from_field)
        try:
            object_id = field.to_python(object_id)
            obj = queryset.get(**{field.name: object_id})
            return obj.get_instance()
        except (model.DoesNotExist, ValidationError, ValueError):
            return None

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'section' and not request.user.has_superpowers:
            sections = get_sections_for_user(request.user)
            kwargs["queryset"] = sections
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # extra urls

    def get_urls(self):
        urls = super().get_urls()
        extra_urls = [
            path('<int:parent_pk>/canned-answer/<int:pk>/<str:movement>/',
                 self.admin_site.admin_view(self.reorder_canned_answers),
                 name='dmpt-question-cannedanswer-reorder'),
        ]
        return extra_urls + urls

    # display fields

    def get_mount(self, obj):
        return obj.eestore.eestore_type if obj.eestore else ''
    get_mount.short_description = 'EEStore'  # type: ignore
    get_mount.admin_order_field = 'eestore'  # type: ignore

    # actions

    def toggle_on_trunk(self, request, queryset):
        for q in queryset.all():
            q.on_trunk = not q.on_trunk
            q.save()
    toggle_on_trunk.short_description = 'Toggle whether on trunk'  # type: ignore


@admin.register(ExplicitBranch)
class ExplicitBranchAdmin(admin.ModelAdmin):
    search_fields = ('current_question', 'next_question')
    list_display = ('current_question', 'category', 'condition', 'next_question', 'id')

    def get_model_perms(self, request):
        """Hide the model from the list of models"""
        return {}
