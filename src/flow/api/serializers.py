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
        fields = [
            'id',
            'url',
            'fsa',
            'slug',
            'start',
            'end',
            'depends',
        ]


class EdgeSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='node-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Edge
        fields = [
            'id',
            'url',
            'condition',
            'prev_node',
            'next_node',
        ]


class FSASerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='fsa-detail',
        lookup_field='pk'
    )

    class Meta:
        model = FSA
        fields = [
            'id',
            'url',
            'slug',
        ]
