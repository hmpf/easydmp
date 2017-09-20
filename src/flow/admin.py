from django.contrib import admin

from .models import Node
from .models import Edge
from .models import FSA


class EdgeAdmin(admin.ModelAdmin):
    list_display = ['condition', 'prev_node', 'next_node']
admin.site.register(Edge, EdgeAdmin)


class NodeAdmin(admin.ModelAdmin):
    list_display = ['slug', 'depends', 'fsa']
    list_filter = ['fsa']
admin.site.register(Node, NodeAdmin)


class FSAAdmin(admin.ModelAdmin):
    list_display = ['id',]
admin.site.register(FSA, FSAAdmin)
