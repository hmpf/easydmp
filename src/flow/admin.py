from django.contrib import admin

from .models import Node
from .models import Edge
from .models import FSA


class PrevEdgeInline(admin.StackedInline):
    model = Edge
    fk_name = 'prev_node'


class EdgeAdmin(admin.ModelAdmin):
    list_display = ['condition', 'prev_node', 'next_node']
admin.site.register(Edge, EdgeAdmin)

class NodeInline(admin.StackedInline):
    model = Node


class NodeAdmin(admin.ModelAdmin):
    list_display = ['slug', 'depends', 'fsa']
    list_filter = ['fsa']
    inlines = [PrevEdgeInline]
admin.site.register(Node, NodeAdmin)


class FSAAdmin(admin.ModelAdmin):
    list_display = ['slug', 'id']
    inlines = [NodeInline]
admin.site.register(FSA, FSAAdmin)
