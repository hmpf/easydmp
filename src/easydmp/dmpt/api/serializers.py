from rest_framework import serializers

from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.forms import INPUT_TYPE_TO_FORMS


__all__ = [
    'TemplateSerializer',
    'SectionSerializer',
    'LightQuestionSerializer',
    'HeavyQuestionSerializer',
    'CannedAnswerSerializer',
]


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:template-detail',
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
        view_name='v1:section-detail',
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


class LightQuestionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:question-detail',
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


class HeavyQuestionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:question-detail',
        lookup_field='pk'
    )
    answer_schema = serializers.SerializerMethodField()

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
            'help_text',
            'comment',
            'node',
            'answer_schema',
        ]

    def get_answer_schema(self, obj):
        form = INPUT_TYPE_TO_FORMS.get(obj.input_type, None)
        if not form:
            return {}
        boundform = form(question=obj)
        serialized_form = boundform.serialize_form()
        return serialized_form


class CannedAnswerSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:question-detail',
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
