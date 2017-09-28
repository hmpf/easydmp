from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'template', 'added_by', 'added']
    readonly_fields = ['added', 'added_by']
