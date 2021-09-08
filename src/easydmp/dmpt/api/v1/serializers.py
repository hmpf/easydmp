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

    def get_answer_schema(self, obj):
        input_type = Question.INPUT_TYPES.get(obj.input_type, None)
        if not input_type:
            return {}
        boundform = input_type.form(question=obj)
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
