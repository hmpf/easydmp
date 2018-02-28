from django.contrib import admin


@admin.register
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'url']
