from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from easydmp.eestore.models import EEStoreMount
from easydmp.lib.api.serializers import SelfHyperlinkedModelSerializer
from easydmp.lib.api.serializers import SelfHyperlinkedRelatedField
from ...models import Template
from ...models import TemplateImportMetadata
from ...models import Section
from ...models import Question
from ...models import CannedAnswer
from ...models import ExplicitBranch


__all__ = [
    'TemplateSerializer',
    'TemplateImportMetadataSerializer',
    'SectionSerializer',
    'LightQuestionSerializer',
    'HeavyQuestionSerializer',
    'CannedAnswerSerializer',
    'ExplicitBranchSerializer',
]


class TemplateSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = Template
        fields = [
            'id',
            'self',
            'title',
            'import_metadata',
            'abbreviation',
            'description',
            'more_info',
            'reveal_questions',
            'version',
            'created',
            'locked',
            'published',
            'retired',
        ]


class TemplateImportMetadataSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = TemplateImportMetadata
        fields = [
            'id',
            'self',
            'origin',
            'original_template_pk',
            'originally_cloned_from',
            'imported',
            'imported_via',
            'template',
            'mappings',
        ]


class SectionSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = Section
        fields = [
            'id',
            'self',
            'template',
            'label',
            'title',
            'introductory_text',
            'comment',
            'position',
            'super_section',
            'section_depth',
            'branching',
            'optional',
            'repeatable',
            'modified',
        ]


class LightQuestionSerializer(SelfHyperlinkedModelSerializer):
    template = SelfHyperlinkedRelatedField(
        source='section.template', read_only=True,
        view_name='v2:template-detail',
    )
    input_type = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'self',
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
            'self',
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


class CannedAnswerSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = CannedAnswer
        fields = [
            'id',
            'self',
            'question',
            'choice',
            'canned_text',
            'comment',
        ]


class ExplicitBranchSerializer(SelfHyperlinkedModelSerializer):

    class Meta:
        model = ExplicitBranch
        fields = [
            'id',
            'self',
            'current_question',
            'category',
            'condition',
            'next_question',
        ]
