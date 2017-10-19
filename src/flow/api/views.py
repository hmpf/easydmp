from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from flow.api.serializers import *
from flow.models import Node
from flow.models import Edge
from flow.models import FSA


class NodeViewSet(ReadOnlyModelViewSet):
    queryset = Node.objects.all()
    serializer_class = NodeSerializer


class EdgeViewSet(ReadOnlyModelViewSet):
    queryset = Edge.objects.all()
    serializer_class = EdgeSerializer


class FSAViewSet(ReadOnlyModelViewSet):
    queryset = FSA.objects.all()
    serializer_class = FSASerializer
