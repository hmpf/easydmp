from django.contrib import admin

from .models import (
    EEStoreType,
    EEStoreSource,
    EEStoreCache,
    EEStoreMount,
)


@admin.register(EEStoreType)
class EEStoreTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(EEStoreSource)
class EEStoreSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'eestore_type']
    list_filter = ['eestore_type']


@admin.register(EEStoreCache)
class EEStoreCacheAdmin(admin.ModelAdmin):
    list_display = ['name', 'source', 'last_fetched']
    list_filter = ['eestore_type', 'source']
    search_fields = ['name']


@admin.register(EEStoreMount)
class EEStoreMountAdmin(admin.ModelAdmin):
    list_display = ['question', 'eestore_type']
    list_filter = ['eestore_type']
