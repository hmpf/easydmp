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
    list_filter = ('question',)


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
    list_filter = ['section']
    inlines = [CannedAnswerInline]
