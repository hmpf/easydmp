from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers
from rest_framework.fields import JSONField

from easydmp.auth.api.views import UserSerializer

from easydmp.plan.models import Plan


class PlanSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plan-detail',
        lookup_field='pk',
    )
    template = serializers.HyperlinkedRelatedField(
        view_name='template-detail',
        lookup_field='pk',
        many=False,
        read_only=True,
    )
    data = JSONField(binary=False)
    previous_data = JSONField(binary=False)
    added_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='pk',
        many=False,
        read_only=True,
    )
    modified_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='pk',
        many=False,
        read_only=True,
    )

    class Meta:
        model = Plan
        fields = [
            'url',
            'title',
            'abbreviation',
            'version',
            'template',
            'data',
            'previous_data',
            'added',
            'added_by',
            'modified',
            'modified_by',
        ]


class PlanViewSet(ReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
