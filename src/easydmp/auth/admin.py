from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class EasyDMPUserAdmin(UserAdmin):
    date_hierarchy = 'date_joined'
