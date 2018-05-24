from rest_framework import serializers
from rest_framework.fields import JSONField
from rest_framework.viewsets import ReadOnlyModelViewSet

from django_filters.rest_framework.filterset import FilterSet

from easydmp.auth.api.views import UserSerializer

from easydmp.plan.models import Plan


class PlanFilter(FilterSet):

    class Meta:
        model = Plan
        fields = {
            'added': ['lt', 'gt', 'lte', 'gte'],
            'modified': ['lt', 'gt', 'lte', 'gte'],
            'locked': ['lt', 'gt', 'lte', 'gte'],
            'published': ['lt', 'gt', 'lte', 'gte'],
        }


class LightPlanSerializer(serializers.HyperlinkedModelSerializer):
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

    class Meta:
        model = Plan
        fields = [
            'id',
            'uuid',
            'url',
            'title',
            'abbreviation',
            'version',
            'template',
            'added',
            'modified',
            'locked',
            'published',
        ]

class HeavyPlanSerializer(LightPlanSerializer):
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
    locked_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='pk',
        many=False,
        read_only=True,
    )
    published_by = serializers.HyperlinkedRelatedField(
        view_name='user-detail',
        lookup_field='pk',
        many=False,
        read_only=True,
    )

    class Meta:
        model = Plan
        fields = [
            'id',
            'uuid',
            'url',
            'title',
            'abbreviation',
            'version',
            'template',
            'data',
            'previous_data',
            'generated_html',
            'doi',
            'added',
            'added_by',
            'modified',
            'modified_by',
            'locked',
            'locked_by',
            'published',
            'published_by',
        ]


class PlanViewSet(ReadOnlyModelViewSet):
    filter_class = PlanFilter
    serializer_class = HeavyPlanSerializer

# 
#     def get_serializer_class(self):
#         if self.action == 'retrieve':
#             return HeavyPlanSerializer
#         return LightPlanSerializer

    def get_queryset(self):
        qs = Plan.objects.exclude(published=None)
        if self.request.user.is_authenticated():
            user_groups = self.request.user.groups.all()
            qs = qs | Plan.objects.filter(
                published=None,
                editor_group__in=user_groups,
            )
        return qs
