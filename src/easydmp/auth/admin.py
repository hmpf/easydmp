from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext, ugettext_lazy as _

from rest_framework.authtoken.admin import TokenAdmin

from .models import User


@admin.register(User)
class EasyDMPUserAdmin(UserAdmin):
    change_form_template = "admin/auth/user/change_form.html"  # For Django-su
    change_list_template = "admin/auth/user/change_list.html"  # For Django-su
    date_hierarchy = 'date_joined'
    list_display = ('username', 'email', 'full_name', 'is_staff')
    search_fields = ('username', 'full_name', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups',)}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


TokenAdmin.raw_id_fields = ['user']
