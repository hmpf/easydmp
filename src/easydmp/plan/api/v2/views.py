from django_filters.rest_framework import DjangoFilterBackend
from django_filters.rest_framework.filterset import FilterSet
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from easydmp.auth.api.permissions import IsAuthenticatedAndActive
from easydmp.lib.api.pagination import ToggleablePageNumberPaginationV2
from easydmp.lib.api.renderers import StaticPlaintextRenderer, HTML2PDFRenderer
from easydmp.plan.models import Plan
from easydmp.plan.models import AnswerSet
from easydmp.plan.models import Answer
from easydmp.plan.views import generate_pretty_exported_plan
from easydmp.plan.utils import GenerateRDA10
from . import serializers


class PlanFilter(FilterSet):

    class Meta:
        model = Plan
        fields = {
            'added': ['lt', 'gt', 'lte', 'gte'],
            'modified': ['lt', 'gt', 'lte', 'gte'],
            'locked': ['lt', 'gt', 'lte', 'gte'],
            'published': ['lt', 'gt', 'lte', 'gte'],
            'template': ['exact'],
            'valid': ['exact'],
        }


class PlanViewSet(ReadOnlyModelViewSet):
    filter_class = PlanFilter
    search_fields = ['=id', 'title', '=abbreviation', 'search_data']
    serializer_class = serializers.HeavyPlanSerializer
    pagination_class = ToggleablePageNumberPaginationV2
    export_renderers = [
        StaticHTMLRenderer,
        StaticPlaintextRenderer,
        HTML2PDFRenderer,
    ]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.HeavyPlanSerializer
        return serializers.LightPlanSerializer

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

    @action(detail=True, methods=['get'], renderer_classes=export_renderers,
            permission_classes=[IsAuthenticatedAndActive])
    def export(self, request, pk=None, format=None, **kwargs):
        # WTF: Makes "export/?format=txt" behave the same as "export.txt"
        if not format:
            get_format = request.GET.get('format', None) or 'html'
            if get_format in ('html', 'txt', 'pdf'):
                format = get_format
        template_name = 'easydmp/plan/generated_plan.html'
        plan = self.get_object()
        if format == 'txt':
            template_name = 'easydmp/plan/generated_plan.txt'
        blob = generate_pretty_exported_plan(plan, template_name)
        response = Response(blob)
        response['Content-Disposition'] = f'inline; filename=plan-{plan.pk}.{format}'
        return response


class AnswerSetFilter(FilterSet):

    class Meta:
        model = AnswerSet
        fields = {
            'plan': ['exact'],
            'section': ['exact'],
            'section__template': ['exact'],
            'valid': ['exact'],
            'last_validated': ['lt', 'gt', 'lte', 'gte'],
        }


class AnswerSetViewSet(ReadOnlyModelViewSet):
    filter_class = AnswerSetFilter
    serializer_class = serializers.AnswerSetSerializer
    queryset = AnswerSet.objects.order_by('pk')
    pagination_class = ToggleablePageNumberPaginationV2
    search_fields = ['data', 'previous_data']


class AnswerFilter(FilterSet):

    class Meta:
        model = Answer
        fields = {
            'answerset': ['exact'],
            'answerset__plan': ['exact'],
            'question': ['exact'],
            'question__section': ['exact'],
            'question__section__template': ['exact'],
            'valid': ['exact'],
            'last_validated': ['lt', 'gt', 'lte', 'gte'],
        }


class AnswerViewSet(ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filter_class = AnswerFilter
    serializer_class = serializers.AnswerSerializer
    queryset = Answer.objects.order_by('answerset_id', 'question_id', 'pk')
    pagination_class = ToggleablePageNumberPaginationV2
