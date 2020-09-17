from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.site.api.renderers import DotPDFRenderer
from easydmp.site.api.renderers import DotPNGRenderer
from easydmp.site.api.renderers import DotDOTRenderer
from easydmp.site.api.renderers import DotSVGRenderer

from easydmp.dmpt.api.serializers import *
from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.models import ExplicitBranch


class TemplateViewSet(ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    search_fields = ['title']


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
