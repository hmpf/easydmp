# -*- coding: utf-8 -*-
import copy
import warnings
from urllib.parse import parse_qsl

from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django import forms
from django.template.response import TemplateResponse
from django.http.response import HttpResponseRedirect
from django.http import Http404
from django.urls import reverse, path
from django.utils.html import format_html, mark_safe

from guardian.shortcuts import get_objects_for_user, assign_perm

from easydmp.auth.utils import set_user_object_permissions
from easydmp.eestore.models import EEStoreMount
from easydmp.eventlog.utils import log_event
from easydmp.lib.admin import FakeBooleanFilter
from easydmp.lib.admin import PublishedFilter
from easydmp.lib.admin import RetiredFilter
from easydmp.lib.admin import LockedFilter
from easydmp.lib.admin import ImportedFilter
from easydmp.lib.admin import AdminConvenienceMixin
from easydmp.lib.admin import ObjectPermissionModelAdmin
from easydmp.lib.admin import SetObjectPermissionModelAdmin
from easydmp.lib import get_model_name

from .import_template import deserialize_template_export
from .import_template import import_or_get_template
from .import_template import TemplateImportError
from .models import Template
from .models import TemplateImportMetadata
from .models import Section
from .models import ExplicitBranch
from .models import Question
from .models import QuestionType
from .models import CannedAnswer
from .positioning import Move

"""
The admin is simplified for non-superusers. Branching sections are disallowed,
hence all questions are on_trunk.
"""


def get_templates_for_user(user, verbs=None):
    if user.has_superpowers:
        return Template.objects.all()
    good_verbs = ('change', 'add', 'delete', 'view', 'use')
    if verbs is None:
        verbs = ('change',)
    permission_set = set()
    for verb in verbs:
        if verb not in good_verbs:
            verb = 'change'
        permission_set.add(f'dmpt.{verb}_template')
    templates = get_objects_for_user(
        user,
        permission_set,
        any_perm=True,
        accept_global_perms=False,
    )
    return templates


def get_sections_for_user(user, verbs=None):
    templates = get_templates_for_user(user, verbs)
    return Section.objects.filter(template__in=templates)


def get_questions_for_user(user, verbs=None):
    sections = get_sections_for_user(user, verbs)
    return Question.objects.filter(section__in=sections)


def get_canned_answers_for_user(user, verbs=None):
    questions = get_questions_for_user(user, verbs)
    return CannedAnswer.objects.filter(question__in=questions)


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

    * permissions_checker: the name (as a string) of a function that takes
     a user and an iterable of permission verbs (one or more of 'add', 'view',
     'change', 'delete', 'use'). It returns an iterable of model instances that
     has at least one of the permissions. Used to visually disable all buttons
     if the user does not have permission to change the object.
    * ordering_fieldname: the field that holds the order, by default "position"
    * item: a method that prints a human readable summary of the object to be
      ordered, by default ``str(obj)``

    If you extend an BaseOrderingInline to work as a normal inline, you should
    probably also override the following:

    * fields: must contain "movement", for the movement buttons, and
      ordering_fieldname
    * readonly_fields: must always contain at least "movement" and
      ordering_fieldname
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
    permissions_checker = None
    MOVEMENT_BUTTONS = {
        Move.UP: {'active': True, 'icon': '⭡'},
        Move.TOP: {'active': True, 'icon': '⭱'},
        Move.DOWN: {'active': True, 'icon': '⭣'},
        Move.BOTTOM: {'active': True, 'icon': '⭳'},
    }

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

    def has_change_permission(self, request, obj=None):
        if obj and isinstance(self.permissions_checker, str):
            allowed_objs = globals()[self.permissions_checker](request.user)
            self.changeable = obj in allowed_objs
        else:
            self.changeable = super().has_change_permission(request, obj)
        return self.changeable

    @mark_safe
    def movement(self, obj):
        buttons = copy.deepcopy(self.MOVEMENT_BUTTONS)
        # Deactivate invalid movement directions
        if obj.is_readonly or not self.changeable:
            buttons[Move.UP]['active'] = False
            buttons[Move.TOP]['active'] = False
            buttons[Move.DOWN]['active'] = False
            buttons[Move.BOTTOM]['active'] = False
        else:
            parent = self.get_parent(obj)
            order = self.get_order(parent)
            obj_index = order.index(obj.pk)
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
    change_form_template = 'admin/dmpt/guardian-model-change_form.html'
    obj_perms_manage_group_template = 'admin/dmpt/guardian-model-obj_perms_manage_group.html'
    obj_perms_manage_user_template = 'admin/dmpt/guardian-model-obj_perms_manage_user.html'
    obj_perms_manage_template = 'admin/dmpt/guardian-model-obj_perms_manage.html'
    message_cannot_delete = ('The {} cannot be deleted because it is'
                             ' in use by one or more plans.')
    permissions_checker = None

    def has_change_permission(self, request, obj=None):
        if obj:
            if obj.is_readonly:
                return False
            if isinstance(self.permissions_checker, str):
                allowed_objs = globals()[self.permissions_checker](request.user)
                return obj in allowed_objs
        return super().has_change_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        if obj and isinstance(self.permissions_checker, str):
            allowed_objs = globals()[self.permissions_checker](request.user, ['view'])
            return obj in allowed_objs
        return super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj:
            if isinstance(self.permissions_checker, str):
                allowed_objs = globals()[self.permissions_checker](request.user, ['delete'])
                return obj in allowed_objs
            if obj.is_readonly and obj.in_use():
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
    permissions_checker = 'get_templates_for_user'

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
    readonly_fields = ['uuid']
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
            'fields': ('title', 'abbreviation', 'uuid','version', 'description',
                       'more_info', 'reveal_questions', 'domain_specific',
                       'locked', 'published', 'retired'),
        }),
        ('Advanced', {
            'fields': ('cloned_from', 'cloned_when',),
            'classes': ('collapse',),
        }),
    )
    permissions_checker = 'get_templates_for_user'

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Section reordering supermagic

    def reorder_sections(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        if parent.is_readonly or parent not in get_sections_for_user(request.user):
            return HttpResponseRedirect(url)
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
                        tim = import_or_get_template(serialized_dict, via='admin')
                        if w:
                            messages.warning(request, w[-1].message)
                except TemplateImportError as e:
                    messages.error(request, str(e))
                    return HttpResponseRedirect(url_on_error)
                template = tim.template
                msg = f'Template "{template}" successfully imported.'
                messages.success(request, msg)
                log_event(request.user, 'import', target=template,
                          timestamp=tim.imported,
                          template=msg[:-1])
                # for admin.LogEntry
                self.log_change(request, template, {'added': {}})
                if not request.user.has_superpowers:
                    extra_permissions = getattr(self, 'set_permissions', [])
                    # TD's may view and use the imported template regardless
                    assign_perm('view_template', request.user, template)
                    for perm in extra_permissions:
                        assign_perm(perm, request.user, template)
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
    permissions_checker = 'get_sections_for_user'

    def get_order(self, parent):
        return parent.get_section_order()

    def item(self, obj):
        return obj.full_title()


class QuestionOrderingInline(BaseOrderingInline):
    model = Question
    fk_name = 'section'
    movement_view_pattern = '%s:%s-section-question-reorder'
    verbose_name_plural = "Question ordering"
    permissions_checker = 'get_sections_for_user'

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
        'super_section_id',
    )
    list_display_links = ('template', 'section_depth', 'id', 'position')
    list_filter = ('branching', 'template', 'optional', 'repeatable')
    ordering = ('template', 'position',)
    search_fields = [
        '=id',
        'title',
    ]
    fieldsets = (
        (None, {
            'fields': ('template', 'title', 'position', 'label', 'branching',
                       'optional', 'repeatable', 'introductory_text', 'comment',
                       'identifier_question'),
        }),
        ('Super section', {
            'fields': ('super_section', 'section_depth'),
        }),
        ('Options for optional questions', {
            'fields': ('optional_canned_text',),
            'classes': ('collapse',),
        }),
        ('Advanced', {
            'fields': ('cloned_from', 'cloned_when'),
            'classes': ('collapse',),
        }),
    )
    inlines = [SubsectionOrderingInline, QuestionOrderingInline]
    readonly_fields = ['cloned_from', 'cloned_when', 'position']
    _model_slug = 'section'
    permissions_checker = 'get_sections_for_user'

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Reordering supermagic

    def reorder_sections(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        if parent.is_readonly or parent not in get_sections_for_user(request.user):
            return HttpResponseRedirect(url)
        try:
            parent.reorder_sections(pk, movement)
        except ValueError as e:
            self.message_user(request, str(e), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    def reorder_questions(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        if parent.is_readonly or parent not in get_questions_for_user(request.user):
            return HttpResponseRedirect(url)
        try:
            parent.reorder_questions(pk, movement)
        except ValueError as error:
            self.message_user(str(error), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    # Overrides

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_superpowers:
            return self.readonly_fields
        return self.readonly_fields + ['optional', 'repeatable']

    def get_limited_queryset(self, request):
        return get_sections_for_user(request.user, ('change', 'view'))

    def get_form(self, request, obj=None, **kwargs):
        request.instance = obj
        return super().get_form(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        # Ensure that only templates the user are allowed to use are available
        templates = get_templates_for_user(request.user)
        # Limit templates by the template filter, if any
        filters = dict(parse_qsl(request.GET.get('_changelist_filters', '')))
        template_id = int(filters.get('template__id__exact', 0))
        if template_id:
            templates = templates.filter(id=template_id)
            if not templates.exists():
                raise Http404

        if db_field.name == 'template':
            # Limit to allowable templates
            field.queryset = templates
            return field
        instance = request.instance
        if db_field.name == 'super_section':
            if instance:
                # Limit to existing sections of the template and exclude self
                qs = field.queryset.filter(template_id=instance.template_id)
                field.queryset = qs.exclude(id=instance.id)
            else:
                # Limit to allowable sections
                field.queryset = field.queryset.filter(template__in=templates)
            return field
        if db_field.name == 'identifier_question':
            if instance:
                # Limit to existing questions of this section
                qs = field.queryset.filter(section_id=instance.id)
                field.queryset = field.queryset.filter(section_id=instance.id)
            else:
                # No section set, no questions available
                field.queryset = field.queryset.none()
        return field

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

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_superpowers:
            return ()
        return [f.name for f in self.model._meta.fields]

    # overriden to hide add/change buttons on next_question in formset
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Hook for specifying the form Field instance for a given database Field
        instance.

        If kwargs are given, they're passed to the form Field's constructor.
        """
        # If the field specifies choices, we don't need to look for special
        # admin widgets - we just need to use a select widget of some kind.
        if db_field.choices:
            return self.formfield_for_choice_field(db_field, request, **kwargs)

        # ForeignKey or ManyToManyFields
        if isinstance(db_field, (models.ForeignKey, models.ManyToManyField)):
            # Combine the field kwargs with any options for formfield_overrides.
            # Make sure the passed in **kwargs override anything in
            # formfield_overrides because **kwargs is more specific, and should
            # always win.
            if db_field.__class__ in self.formfield_overrides:
                kwargs = {**self.formfield_overrides[db_field.__class__], **kwargs}

            # Get the correct formfield.
            if isinstance(db_field, models.ForeignKey):
                formfield = self.formfield_for_foreignkey(db_field, request, **kwargs)
            elif isinstance(db_field, models.ManyToManyField):
                formfield = self.formfield_for_manytomany(db_field, request, **kwargs)

            return formfield

        # If we've got overrides for the formfield defined, use 'em. **kwargs
        # passed to formfield_for_dbfield override the defaults.
        for klass in db_field.__class__.mro():
            if klass in self.formfield_overrides:
                kwargs = {**copy.deepcopy(self.formfield_overrides[klass]), **kwargs}
                return db_field.formfield(**kwargs)

        # BIG BLOCK REMOVED, added buttosn to related fields

        # For any other type of field, just call its formfield() method.
        return db_field.formfield(**kwargs)


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        filters = dict(parse_qsl(request.GET.get('_changelist_filters', '')))
        if db_field.name == 'next_question':
            sections = get_sections_for_user(request.user)
            if template_id := int(filters.get('template', 0)):
                sections = sections.filter(template_id=template_id)
            if section_id := int(filters.get('section', 0)):
                sections = sections.filter(id=section_id)
            field.queryset = field.queryset.filter(section__in=sections)
        return field


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
    permissions_checker = 'get_questions_for_user'

    def get_order(self, parent):
        return parent.get_canned_answer_order()


@admin.register(QuestionType)
class QuestionTypeAdmin(admin.ModelAdmin):
    list_filter = ['allow_notes', 'branching_possible', 'can_identify']
    list_display = ['id'] + list_filter
    readonly_fields = list_display


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
    )
    list_select_related = ['section']
    list_display_links = ('position', 'id', 'question')
    search_fields = [
        '=id',
        'question',
        'section__title',
    ]
    readonly_fields = ['cloned_from', 'cloned_when', 'position']
    actions = [
        'toggle_on_trunk',
    ]
    list_filter = [
        'on_trunk',
        'optional',
        QuestionTemplateFilter,
        QuestionSectionFilter,
        'input_type',
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
                       'question', 'has_notes', 'on_trunk', 'optional',
                       'help_text', 'framing_text', 'comment',),
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
    permissions_checker = 'get_questions_for_user'

    class Media:
        css = {
            "all": ("/static/admin/movement.css",)
        }

    # Reordering supermagic

    def reorder_canned_answers(self, request, parent_pk, pk, movement):
        url = self.get_change_url(parent_pk)
        parent = self.model.objects.get(pk=parent_pk)
        if parent.is_readonly or parent not in get_canned_answers_for_user(request.user):
            return HttpResponseRedirect(url)
        try:
            parent.reorder_canned_answers(pk, movement)
        except ValueError as error:
            self.message_user(str(error), level=messages.WARNING)
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(url)

    # overrides

    def get_readonly_fields(self, request, obj=None):
        if not request.user.has_superpowers:
            return self.readonly_fields + ['on_trunk']
        return self.readonly_fields

    def get_limited_queryset(self, request):
        return get_questions_for_user(request.user, ('change', 'view'))

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
        field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        filters = dict(parse_qsl(request.GET.get('_changelist_filters', '')))
        if db_field.name == 'section':
            sections = get_sections_for_user(request.user)
            if template_id := int(filters.get('template', 0)):
                sections = sections.filter(template_id=template_id)
            if section_id := int(filters.get('section', 0)):
                sections = sections.filter(id=section_id)
            field.queryset = sections
        return field

    def save_model(self, request, obj, form, change):
        if not change:
            position = obj.get_next_question_position()
            obj.position = position
        super().save_model(request, obj, form, change)

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
