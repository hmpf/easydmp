from django.contrib import admin

from .models import PlanEditorInvitation


@admin.register(PlanEditorInvitation)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['plan', 'email_address', 'invited_by', 'created', 'sent', 'used']
    list_filter = ['plan']
