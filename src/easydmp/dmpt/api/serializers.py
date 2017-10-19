from rest_framework import serializers

from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer


__all__ = [
    'TemplateSerializer',
    'SectionSerializer',
    'QuestionSerializer',
    'CannedAnswerSerializer',
]


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='template-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Template
        fields = [
            'id',
            'url',
            'title',
            'abbreviation',
            'version',
            'created',
            'published',
        ]


class SectionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='section-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Section
        fields = [
            'id',
            'url',
            'template',
            'title',
            'position',
            'introductory_text',
            'comment',
        ]


class QuestionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='question-detail',
        lookup_field='pk'
    )

    class Meta:
        model = Question
        fields = [
            'id',
            'url',
            'input_type',
            'section',
            'position',
            'label',
            'question',
            'framing_text',
            'comment',
            'node',
        ]



class CannedAnswerSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='question-detail',
        lookup_field='pk'
    )

    class Meta:
        model = CannedAnswer
        fields = [
            'id',
            'url',
            'question',
            'choice',
            'canned_text',
            'comment',
            'edge',
        ]
