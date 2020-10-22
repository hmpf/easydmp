from django_filters.rest_framework.filterset import FilterSet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.fields import JSONField
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ReadOnlyModelViewSet

from easydmp.auth.api.v2.views import UserSerializer
from easydmp.lib.api.pagination import ToggleablePageNumberPagination
from easydmp.plan.models import Plan
from easydmp.plan.models import SectionValidity
from easydmp.plan.models import QuestionValidity
from easydmp.plan.utils import GenerateRDA10


class LightSectionValiditySerializer(serializers.ModelSerializer):

    class Meta:
        model = SectionValidity
        fields = [
            'id',
            'section',
            'valid',
            'last_validated',
        ]


class LightQuestionValiditySerializer(serializers.ModelSerializer):

    class Meta:
        model = QuestionValidity
        fields = [
            'id',
            'question',
            'valid',
            'last_validated',
        ]


class PlanFilter(FilterSet):

    class Meta:
        model = Plan
        fields = {
            'added': ['lt', 'gt', 'lte', 'gte'],
            'modified': ['lt', 'gt', 'lte', 'gte'],
            'locked': ['lt', 'gt', 'lte', 'gte'],
            'published': ['lt', 'gt', 'lte', 'gte'],
            'template': ['exact'],
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
    generated_html_url = serializers.SerializerMethodField()

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
            'generated_html_url',
            'valid',
            'last_validated',
            'added',
            'modified',
            'locked',
            'published',
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_generated_html_url(self, obj):
        return reverse( 'generated_plan_html', kwargs={'plan': obj.id},
                       request=self.context['request'])


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
    section_validity = LightSectionValiditySerializer(many=True, read_only=True)
    question_validity = LightQuestionValiditySerializer(many=True, read_only=True)

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
            'section_validity',
            'question_validity',
            'data',
            'previous_data',
            'generated_html',
            'generated_html_url',
            'valid',
            'last_validated',
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
    search_fields = ['=id', 'title', '=abbreviation', 'search_data']
    serializer_class = HeavyPlanSerializer
    pagination_class = ToggleablePageNumberPagination

# 
#     def get_serializer_class(self):
#         if self.action == 'retrieve':
#             return HeavyPlanSerializer
#         return LightPlanSerializer

    def get_queryset(self):
        qs = Plan.objects.all()
        if self.request.user.is_authenticated:
            pas = self.request.user.plan_accesses.all()
            qs = qs | Plan.objects.filter(accesses__in=pas)
        return qs.distinct()

    @action(detail=True, methods=['get'], renderer_classes=[JSONRenderer])
    def export_rda(self, request, pk=None, **kwargs):
        plan = self.get_object()
        rda = GenerateRDA10(plan)
        return Response(rda.get_dmp())
