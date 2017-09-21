# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import Template, Section, Question, CannedAnswer


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = (
        'title',
    )


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = (
        'template',
        'position',
        'title',
    )
    list_filter = ('template',)


@admin.register(CannedAnswer)
class CannedAnswerAdmin(admin.ModelAdmin):
    list_display = (
        'question',
        'choice',
        'edge',
    )
    actions = [
        'create_edge',
        'update_edge',
    ]
    list_filter = ('question',)

    def create_edge(self, request, queryset):
        for q in queryset.all():
            if not q.edge:
                q.create_edge()
    create_edge.short_description = 'Create edge'

    def update_edge(self, request, queryset):
        for q in queryset.all():
            if q.edge:
                q.update_edge()
            else:
                q.create_edge()
    update_edge.short_description = 'Update edge'


class CannedAnswerInline(admin.StackedInline):
    model = CannedAnswer


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'position',
        'section',
        'label',
        'question',
        'input_type',
        'node',
    )
    actions = [
        'create_node',
    ]
    list_filter = ['section']
    inlines = [CannedAnswerInline]

    def create_node(self, request, queryset):
        for q in queryset.all():
            if not q.node:
                q.create_node()
    create_node.short_description = 'Create node'


