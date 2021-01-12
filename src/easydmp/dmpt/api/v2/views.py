from urllib.parse import urlparse

from django.db import IntegrityError

from drf_spectacular.utils import extend_schema
import requests
import requests.exceptions
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.lib.api.renderers import DotPDFRenderer
from easydmp.lib.api.renderers import DotPNGRenderer
from easydmp.lib.api.renderers import DotDOTRenderer
from easydmp.lib.api.renderers import DotSVGRenderer

from easydmp.dmpt.export_template import ExportSerializer, serialize_template_export
from easydmp.dmpt.import_template import (
    ImportSerializer, deserialize_template_export, import_serialized_export
)
from easydmp.dmpt.models import Template
from easydmp.dmpt.models import TemplateImportMetadata
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.models import ExplicitBranch
from .serializers import *


def get_template_export_from_url(url):
    try:
        with requests.get(url, timeout=0.1) as response:
            response.raise_for_status()
            return deserialize_template_export(response.content)
        return {}
    except requests.exception.Timeout:
        raise ServiceUnavailable(
            detail=f'Could not access {url}, timeout'
        )


class DRFIntegrityError(APIException):
    status_code = 409
    default_detail = 'Could not save changes.'
    default_code = 'database_integrity'


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service temporarily unavailable, try again later.'
    default_code = 'service_unavailable'


class TemplateViewSet(ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    search_fields = ['title']

    @extend_schema(responses=ExportSerializer)
    @action(detail=True, methods=['get'], renderer_classes=[JSONRenderer])
    def export(self, request, pk=None):
        serializer = serialize_template_export(pk)
        return Response(data=serializer.data)

    @action(detail=False, methods=['post'], serializer_class=ImportSerializer, url_path='import', url_name='import')
    def import_template(self, request):
        serializer = ImportSerializer(data=request.POST)
        if serializer.is_valid():
            data = serializer.data
            url = data['url']
            new_title = data.get('new_title', '')
            export_dict = get_template_export_from_url(url)
            if export_dict:
                origin = urlparse(url).netloc
                try:
                    template = import_serialized_export(export_dict, origin=origin, title=new_title, via='API')
                except IntegrityError as e:
                    errormsg = e.args
                    if e.__cause__.__class__.__name__ == 'UniqueViolation':
                        errormsg = {
                            'detail': 'A template with this id and origin already exists',
                            'code': 'already_exists'
                        }
                    raise DRFIntegrityError(**errormsg)
                serializer = TemplateSerializer(template)
                headers = {'Location': reverse('v2:template-detail', kwargs={'pk': template.pk}, request=request)}
                return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        return Response(serializer.errors, status=status.HTTP_201_CREATED)


class TemplateImportMetadataViewSet(ReadOnlyModelViewSet):
    queryset = TemplateImportMetadata.objects.all()
    serializer_class = TemplateImportMetadataSerializer


class SectionViewSet(ReadOnlyModelViewSet):
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


class QuestionViewSet(ReadOnlyModelViewSet):
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


class CannedAnswerViewSet(ReadOnlyModelViewSet):
    queryset = CannedAnswer.objects.all()
    serializer_class = CannedAnswerSerializer
    filter_fields = ['question', 'question__input_type', 'question__section',
                     'question__section__template', ]


class ExplicitBranchViewSet(ReadOnlyModelViewSet):
    queryset = ExplicitBranch.objects.select_related('current_question', 'next_question')
    serializer_class = ExplicitBranchSerializer
    filter_fields = ['current_question', 'next_question', 'condition',
                     'category']
    search_fields = ['current_question', 'next_question']
