from rest_framework import serializers

from flow.models import Node
from flow.models import Edge
from flow.models import FSA


__all__ = [
    'NodeSerializer',
    'EdgeSerializer',
    'FSASerializer',
]


class NodeSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='node-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Node
        fields = '__all__'


class EdgeSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='node-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Edge
        fields = '__all__'


class FSASerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='fsa-detail',
        lookup_field='pk'
    )

    class Meta:
        model = FSA
        fields = '__all__'
