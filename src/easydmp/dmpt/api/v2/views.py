from django.db import IntegrityError

from drf_spectacular.utils import extend_schema
import requests
import requests.exceptions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework import parsers, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse

from easydmp.lib.api.renderers import DotPDFRenderer
from easydmp.lib.api.renderers import DotDOTRenderer
from easydmp.lib.api.renderers import DotPNGRenderer
from easydmp.lib.api.renderers import DotSVGRenderer
from easydmp.lib.api.response_exceptions import DRFIntegrityError, ServiceUnavailable
from easydmp.lib.api.serializers import URLSerializer
from easydmp.lib.api.viewsets import AnonReadOnlyModelViewSet

from easydmp.dmpt.export_template import ExportSerializer, serialize_template_export
from easydmp.dmpt.import_template import (
    deserialize_template_export,
    get_stored_template_origin,
    import_serialized_template_export,
    TemplateImportError,
)
from easydmp.dmpt.models import Template
from easydmp.dmpt.models import TemplateImportMetadata
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.models import ExplicitBranch
from .serializers import *


CONNECT_TIMEOUT = 0.1
READ_TIMEOUT = 10
TIMEOUT_TUPLE = (CONNECT_TIMEOUT, READ_TIMEOUT)


def _get_template_export_from_url(url):
    try:
        with requests.get(url, timeout=TIMEOUT_TUPLE) as response:
            response.raise_for_status()
            try:
                export_dict = deserialize_template_export(response.content)
                if export_dict:
                    return export_dict
            except TemplateImportError as e:
                raise ValidationError(e)
        raise ValidationError('Url points to invalid export, cannot import')
    except requests.exceptions.Timeout:
        raise ServiceUnavailable(
            detail=f'Could not access {url}, timeout'
        )


def _import_template(request, export_dict):
    "Import safely in an API"
    assert export_dict, 'No export data'
    # export_dict is not falsey from this point onward
    try:
        origin = get_stored_template_origin(export_dict)
        template = import_serialized_template_export(export_dict, origin=origin, via='API')
        return template
    except IntegrityError as e:
        errormsg = e.args
        if e.__cause__.__class__.__name__ == 'UniqueViolation':
            errormsg = {
                'detail': 'A template with this id and origin already exists',
                'code': 'already_exists'
            }
        raise DRFIntegrityError(**errormsg)
    except TemplateImportError as e:
        errormsg = {
            'detail': str(e),
            'code': 'import_error',
        }
        raise ValidationError(**errormsg)


class TemplateViewSet(AnonReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    search_fields = ['title']

    @extend_schema(responses=ExportSerializer)
    @action(detail=True, methods=['get'], renderer_classes=[JSONRenderer])
    def export(self, request, pk=None):
        serializer = serialize_template_export(pk)
        return Response(data=serializer.data)

    @extend_schema(responses=TemplateSerializer)
    @action(detail=False, methods=['post'], serializer_class=ExportSerializer, parser_classes=[parsers.JSONParser], url_path='import', url_name='template-import-json')
    def import_via_json_post(self, request):
        export_dict = request.data
        template = _import_template(export_dict)
        serializer = TemplateSerializer(template)
        headers = {'Location': reverse('v2:template-detail', kwargs={'pk': template.pk}, request=request)}
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['post'], serializer_class=URLSerializer, parser_classes=[parsers.JSONParser], url_path='import/url', url_name='template-import-url')
    def import_via_url(self, request):
        url_serializer = URLSerializer(data=request.POST)
        url_serializer.is_valid(raise_exception=True)
        # url_serializer is valid from this point onward
        data = url_serializer.data
        url = data['url']
        export_dict = _get_template_export_from_url(url)
        template = _import_template(export_dict)
        serializer = TemplateSerializer(template)
        headers = {'Location': reverse('v2:template-detail', kwargs={'pk': template.pk}, request=request)}
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class TemplateImportMetadataViewSet(AnonReadOnlyModelViewSet):
    queryset = TemplateImportMetadata.objects.all()
    serializer_class = TemplateImportMetadataSerializer


class SectionViewSet(AnonReadOnlyModelViewSet):
    queryset = Section.objects.select_related('template')
    serializer_class = SectionSerializer
    filter_fields = ['template', 'branching']
    search_fields = ['title']
    _formats = {
        'pdf': DotPDFRenderer,
        'png': DotPNGRenderer,
        'dot': DotDOTRenderer,
        'svg': DotSVGRenderer,
    }

    @action(detail=True, methods=['get'], renderer_classes=_formats.values())
    def graph(self, request, pk=None, format=None):
        if format not in self._formats:
            format = 'pdf'
        section = self.get_object()
        dotsource = section.generate_dotsource(debug=True)
        return Response(dotsource)


class QuestionViewSet(AnonReadOnlyModelViewSet):
    queryset = Question.objects.select_related('section', 'section__template')
    filterset_fields = ['input_type', 'on_trunk', 'optional', 'section',
                        'section__template']
    filter_fields = ['input_type', 'on_trunk', 'optional', 'section',
                     'section__template']
    search_fields = ['question']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return HeavyQuestionSerializer
        return LightQuestionSerializer


class CannedAnswerViewSet(AnonReadOnlyModelViewSet):
    queryset = CannedAnswer.objects.all()
    serializer_class = CannedAnswerSerializer
    filter_fields = ['question', 'question__input_type', 'question__section',
                     'question__section__template', ]


class ExplicitBranchViewSet(AnonReadOnlyModelViewSet):
    queryset = ExplicitBranch.objects.select_related('current_question', 'next_question')
    serializer_class = ExplicitBranchSerializer
    filter_fields = ['current_question', 'next_question', 'condition',
                     'category']
    search_fields = ['current_question', 'next_question']
