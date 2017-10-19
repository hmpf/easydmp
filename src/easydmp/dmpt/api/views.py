from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import serializers

from easydmp.dmpt.api.serializers import *
from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer


class TemplateViewSet(ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer


class SectionViewSet(ReadOnlyModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer


class QuestionViewSet(ReadOnlyModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer


class CannedAnswerViewSet(ReadOnlyModelViewSet):
    queryset = CannedAnswer.objects.all()
    serializer_class = CannedAnswerSerializer
