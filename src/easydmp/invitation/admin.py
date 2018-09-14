from django.contrib import admin

from .models import PlanInvitation


@admin.register(PlanInvitation)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['plan', 'email_address', 'type', 'invited_by', 'created', 'sent', 'used']
    search_fields = ['plan__title', 'plan__abbreviation', 'invited_by__username']
    list_filter = ['type',]
