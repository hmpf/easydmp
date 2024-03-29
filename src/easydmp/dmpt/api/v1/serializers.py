from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from easydmp.dmpt.models import Template
from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Question
from easydmp.dmpt.models import CannedAnswer
from easydmp.dmpt.models import ExplicitBranch


__all__ = [
    'TemplateSerializer',
    'SectionSerializer',
    'LightQuestionSerializer',
    'HeavyQuestionSerializer',
    'CannedAnswerSerializer',
    'ExplicitBranchSerializer',
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
            'description',
            'more_info',
            'reveal_questions',
            'version',
            'created',
            'published',
            'retired',
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
            'modified',
        ]


class LightQuestionSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:question-detail',
        lookup_field='pk'
    )
    template = serializers.HyperlinkedRelatedField(
        source='section.template', read_only=True,
        view_name='v1:template-detail',
    )
    input_type = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'url',
            'input_type',
            'template',
            'section',
            'position',
            'label',
            'question',
            'on_trunk',
            'framing_text',
            'optional',
            'optional_canned_text',
            'comment',
        ]

    @extend_schema_field(str)
    def get_input_type(self, obj):
        return obj.input_type_id


class HeavyQuestionSerializer(LightQuestionSerializer):
    answer_schema = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'url',
            'input_type',
            'template',
            'section',
            'position',
            'label',
            'question',
            'on_trunk',
            'framing_text',
            'help_text',
            'optional',
            'optional_canned_text',
            'comment',
            'answer_schema',
        ]

    @extend_schema_field(dict)
    def get_answer_schema(self, obj):
        form_class = obj.get_form_class()
        if not form_class:
            return {}
        boundform = form_class(question=obj)
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
        ]


class ExplicitBranchSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v1:explicitbranch-detail',
        lookup_field='pk'
    )

    class Meta:
        model = ExplicitBranch
        fields = [
            'id',
            'url',
            'current_question',
            'category',
            'condition',
            'next_question',
        ]
