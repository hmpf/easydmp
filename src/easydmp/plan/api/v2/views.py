from django.db import IntegrityError

from django_filters.rest_framework import DjangoFilterBackend
from django_filters.rest_framework.filterset import FilterSet
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework import parsers, status
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse

from easydmp.auth.api.permissions import IsAuthenticatedAndActive
from easydmp.lib.api.pagination import ToggleablePageNumberPaginationV2
from easydmp.lib.api.renderers import StaticPlaintextRenderer, HTML2PDFRenderer
from easydmp.lib.api.response_exceptions import DRFIntegrityError
from easydmp.lib.api.serializers import URLSerializer
from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet
from easydmp.lib.import_export import get_export_from_url
from easydmp.plan.export_plan import serialize_plan_export, SingleVersionExportSerializer
from easydmp.plan.import_plan import (
    deserialize_plan_export,
    get_stored_plan_origin,
    import_serialized_plan_export,
    PlanImportError,
)
from easydmp.plan.models import Plan
from easydmp.plan.models import AnswerSet
from easydmp.plan.models import Answer
from easydmp.plan.views import generate_pretty_exported_plan
from easydmp.rdadcs.lib.exporting import GenerateRDA10
from . import serializers


def _get_plan_export_from_url(url):
    return get_export_from_url(url, deserialize_plan_export)


def _import_plan(request, export_dict):
    "Import safely in an API"
    if not export_dict:
        errormsg = {
            'detail': 'No export data',
            'code': 'import_error',
        }
        raise ValidationError(**errormsg)
    # export_dict is not falsey from this point onward
    try:
        pim = import_serialized_plan_export(export_dict, request.user, via='API')
        return pim
    except IntegrityError as e:
        errormsg = e.args
        if e.__cause__.__class__.__name__ == 'UniqueViolation':
            errormsg = {
                'detail': 'A plan with this id and origin already exists',
                'code': 'already_exists'
            }
        raise DRFIntegrityError(**errormsg)
    except PlanImportError as e:
        errormsg = {
            'detail': str(e),
            'code': 'import_error',
        }
        raise ValidationError(**errormsg)


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


class PlanViewSet(AnonReadOnlyModelViewSet):
    filter_class = PlanFilter
    search_fields = ['=id', 'title', '=abbreviation', 'search_data']
    serializer_class = serializers.HeavyPlanSerializer
    pagination_class = ToggleablePageNumberPaginationV2
    export_renderers = [
        StaticHTMLRenderer,
        StaticPlaintextRenderer,
        HTML2PDFRenderer,
        JSONRenderer,
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
            if get_format in ('html', 'txt', 'pdf', 'json'):
                format = get_format
        if format == 'json':
            # JSON export
            serializer = serialize_plan_export(pk)
            return Response(data=serializer.data)
        template_name = 'easydmp/plan/generated_plan.html'
        plan = self.get_object()
        if format == 'txt':
            template_name = 'easydmp/plan/generated_plan.txt'
        blob = generate_pretty_exported_plan(plan, template_name)
        response = Response(blob)
        response['Content-Disposition'] = f'inline; filename=plan-{plan.pk}.{format}'
        return response

    @extend_schema(request=SingleVersionExportSerializer, responses=serializers.HeavyPlanSerializer)
    @action(detail=False, methods=['post'], serializer_class=SingleVersionExportSerializer, parser_classes=[parsers.JSONParser], url_path='import', url_name='plan-import-json')
    def import_via_json_post(self, request):
        export_dict = request.data
        pim = _import_plan(request, export_dict)
        plan = pim.plan
        serializer = serializers.HeavyPlanSerializer(
            plan,
            context={'request': request}
        )
        headers = {'Location': reverse('v2:plan-detail', kwargs={'pk': plan.pk}, request=request)}
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @extend_schema(request=URLSerializer, responses=serializers.HeavyPlanSerializer)
    @action(detail=False, methods=['post'], serializer_class=URLSerializer, parser_classes=[parsers.JSONParser], url_path='import/url', url_name='plan-import-url')
    def import_via_url(self, request):
        url_serializer = URLSerializer(data=request.data)
        url_serializer.is_valid(raise_exception=True)
        # url_serializer is valid from this point onward
        data = url_serializer.data
        url = data['url']
        export_dict = _get_plan_export_from_url(url)
        pim = _import_plan(request, export_dict)
        plan = pim.plan
        serializer = serializers.HeavyPlanSerializer(
            plan,
            context={'request': request}
        )
        headers = {'Location': reverse('v2:plan-detail', kwargs={'pk': plan.pk}, request=request)}
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


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


class AnswerSetViewSet(AnonReadOnlyModelViewSet):
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


class AnswerViewSet(AnonReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filter_class = AnswerFilter
    serializer_class = serializers.AnswerSerializer
    queryset = Answer.objects.order_by('answerset_id', 'question_id', 'pk')
    pagination_class = ToggleablePageNumberPaginationV2
