from django.http.response import HttpResponseRedirect

from rest_framework.decorators import action
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.site.api.renderers import PDFRenderer
from easydmp.site.api.renderers import PNGRenderer
from easydmp.site.api.renderers import DOTRenderer
from easydmp.site.api.renderers import SVGRenderer

from easydmp.dmpt.api.serializers import *
from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer


class TemplateViewSet(ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    search_fields = ['title']


class SectionViewSet(ReadOnlyModelViewSet):
    queryset = Section.objects.select_related('template')
    serializer_class = SectionSerializer
    filter_fields = ['template', 'branching']
    search_fields = ['title']

    @action(detail=True, methods=['get'], renderer_classes=[
        PDFRenderer,
        PNGRenderer,
        DOTRenderer,
        SVGRenderer,
    ])
    def graph(self, request, pk=None, format=None):
        supported_formats = ('pdf', 'svg', 'png', 'dot')
        format = 'pdf' if not format else format
        if format not in supported_formats:
            format = 'pdf'
        section = self.get_object()
        section.refresh_cached_dotsource(format, debug=True)
        urlpath = section.get_cached_dotsource_urlpath(format)
        return HttpResponseRedirect(urlpath)


class QuestionViewSet(ReadOnlyModelViewSet):
    queryset = Question.objects.select_related('section', 'section__template')
    filterset_fields = ['input_type', 'obligatory', 'optional', 'section',
                        'section__template']
    filter_fields = ['input_type', 'obligatory', 'optional', 'section',
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
