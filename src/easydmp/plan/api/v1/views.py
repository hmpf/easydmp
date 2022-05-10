from django_filters.rest_framework.filterset import FilterSet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.fields import JSONField
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet

from easydmp.lib.api.pagination import ToggleablePageNumberPaginationV1
from easydmp.plan.models import Plan
from easydmp.plan.models import AnswerSet
from easydmp.plan.models import Answer
from easydmp.rdadcs.lib.exporting import GenerateRDA10


class SectionValiditySerializer(serializers.ModelSerializer):

    class Meta:
        model = AnswerSet
        fields = [
            'id',
            'section',
            'valid',
            'last_validated',
        ]


class QuestionValiditySerializer(serializers.ModelSerializer):

    class Meta:
        model = Answer
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
    generated_html_url = serializers.SerializerMethodField()
    generated_pdf_url = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()
    previous_data = serializers.SerializerMethodField()
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
    section_validity = SectionValiditySerializer(many=True, read_only=True, source='answersets')
    question_validity = QuestionValiditySerializer(many=True, read_only=True, source='answers')

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
            'generated_pdf_url',
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
        read_only_fields = ['generated_html']

    @extend_schema_field(OpenApiTypes.URI)
    def get_generated_html_url(self, obj):
        return reverse('generated_plan_html', kwargs={'plan': obj.id},
                       request=self.context['request'])

    @extend_schema_field(OpenApiTypes.URI)
    def get_generated_pdf_url(self, obj):
        return reverse('generated_plan_pdf', kwargs={'plan': obj.id},
                       request=self.context['request'])

    def get_data(self, obj):
        sections = obj.template.sections.prefetch_related('answersets')
        outdict = {}
        for section in sections:
            answerset = section.answersets.filter(plan=obj).order_by('pk').first()
            if answerset:
                outdict.update(**answerset.data)
        return outdict

    def get_previous_data(self, obj):
        sections = obj.template.sections.prefetch_related('answersets')
        outdict = {}
        for section in sections:
            answerset = section.answersets.filter(plan=obj).order_by('pk').first()
            if answerset:
                outdict.update(**answerset.previous_data)
        return outdict


class PlanViewSet(AnonReadOnlyModelViewSet):
    filter_class = PlanFilter
    search_fields = ['=id', 'title', '=abbreviation', 'search_data']
    serializer_class = PlanSerializer
    pagination_class = ToggleablePageNumberPaginationV1

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
