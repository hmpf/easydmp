from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist

from .models import Node
from .models import Edge
from .models import FSA


def has_payload(obj):
    try:
        obj.payload
        return True
    except ObjectDoesNotExist:
        return False
has_payload.short_description = 'Has Payload'
has_payload.boolean = True


class PayloadListFilter(admin.SimpleListFilter):
    title = 'Payload'
    parameter_name = 'payload'

    def lookups(self, request, model_admin):
        return (
            ('True', 'Yes'),
            ('False', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(payload__isnull=False)
        if self.value() == 'False':
            return queryset.filter(payload__isnull=True)
        return queryset


class PrevEdgeInline(admin.StackedInline):
    model = Edge
    fk_name = 'prev_node'


class EdgeAdmin(admin.ModelAdmin):
    list_display = ['condition', 'prev_node', 'next_node', has_payload]
    list_filter = [PayloadListFilter]
admin.site.register(Edge, EdgeAdmin)


class NodeInline(admin.StackedInline):
    model = Node


class NodeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'depends', 'fsa', has_payload]
    list_filter = [PayloadListFilter, 'fsa']
    inlines = [PrevEdgeInline]

admin.site.register(Node, NodeAdmin)


class FSAAdmin(admin.ModelAdmin):
    list_display = ['slug', 'id']
    inlines = [NodeInline]
admin.site.register(FSA, FSAAdmin)
