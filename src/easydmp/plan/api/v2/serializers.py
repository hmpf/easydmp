from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from easydmp.lib.api.serializers import SelfHyperlinkedModelSerializer
from easydmp.lib.api.serializers import SelfModelSerializer
from easydmp.lib.api.serializers import SelfHyperlinkedRelatedField
from easydmp.plan.models import Plan
from easydmp.plan.models import AnswerSet
from easydmp.plan.models import Answer
from easydmp.dmpt.models import Template


class AnswerSerializer(SelfHyperlinkedModelSerializer):
    class Meta:
        model = Answer
        fields = [
            'id',
            'self',
            'answerset',
            'question',
            'valid',
            'last_validated',
        ]
        read_only_fields = fields


class AnswerSetSerializer(SelfHyperlinkedModelSerializer):
    answers = AnswerSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = AnswerSet
        fields = [
            'id',
            'self',
            'identifier',
            'plan',
            'section',
            'parent',
            'data',
            'previous_data',
            'answers',
            'valid',
            'last_validated',
        ]
        read_only_fields = fields


class LightPlanSerializer(SelfHyperlinkedModelSerializer):
    generated_html_url = serializers.SerializerMethodField()
    generated_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = [
            'id',
            'self',
            'uuid',
            'title',
            'abbreviation',
            'version',
            'template',
            'generated_html_url',
            'generated_pdf_url',
            'valid',
            'last_validated',
            'added',
            'modified',
            'locked',
            'published',
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_generated_html_url(self, obj):
        return reverse('v2:plan-export', kwargs={'pk': obj.id, 'format': 'html'},
                       request=self.context['request'])

    @extend_schema_field(OpenApiTypes.URI)
    def get_generated_pdf_url(self, obj):
        return reverse('v2:plan-export', kwargs={'pk': obj.id, 'format': 'pdf'},
                       request=self.context['request'])


class HeavyPlanSerializer(LightPlanSerializer):
    answersets = AnswerSetSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Plan
        fields = [
            'id',
            'self',
            'uuid',
            'title',
            'abbreviation',
            'version',
            'template',
            'answersets',
            'generated_html',
            'generated_html_url',
            'generated_pdf_url',
            'valid',
            'last_validated',
            'doi',
            'added',
            'added_by',
            'modified',
            'modified_by',
            'locked',
            'locked_by',
            'published',
            'published_by',
        ]
