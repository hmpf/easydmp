from django.contrib import admin

from .models import RDADCSKey
from .models import RDADCSQuestionLink
from .models import RDADCSSectionLink
from .models import RDADCSImportMetadata


@admin.register(RDADCSKey)
class RDADCSKeyAdmin(admin.ModelAdmin):
    list_filter = ('repeatable', 'optional', 'input_type')
    list_display = ('__str__', 'path', 'input_type')
    ordering = ('slug',)
    readonly_fields = ('slug', 'repeatable', 'optional')
    search_fields = ('path',)


@admin.register(RDADCSQuestionLink)
class RDADCSQuestionLinkAdmin(admin.ModelAdmin):
    list_display = ('key', 'question')
    list_filter = ('question__section__template', 'question__section')
    raw_id_fields = ('question',)
    search_fields = ('key__path', 'question__question')


@admin.register(RDADCSSectionLink)
class RDADCSSectionLinkAdmin(admin.ModelAdmin):
    list_display = ('key', 'section')
    list_filter = ('section__template',)
    raw_id_fields = ('section',)
    search_fields = ('key__path', 'section__title')


@admin.register(RDADCSImportMetadata)
class RDADCSImportMetadataAdmin(admin.ModelAdmin):
    list_display = ('original_id', 'plan')
    readonly_fields = ('plan', 'original_id', 'original_id_type',
                        'originally_created', 'originally_modified',
                        'original_json', 'imported', 'imported_via')
    filter = ['imported_via']
