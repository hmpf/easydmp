from django.conf import settings

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from easydmp.dmpt.export_template import serialize_template_export, ExportSerializer as TemplateExportSerializer
from easydmp.lib.import_export import get_origin
from easydmp.plan.models import Answer, AnswerSet, Plan


DEFAULT_VARIANT = 'single version'


class MetadataSerializer(serializers.Serializer):

    version = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()
    template_id = serializers.IntegerField(min_value=1)
    template_copy = TemplateExportSerializer(allow_null=True)
    variant = serializers.CharField(default=DEFAULT_VARIANT)

    @extend_schema_field(str)
    def get_version(self, _):
        return settings.VERSION

    @extend_schema_field(str)
    def get_origin(self, _):
        return get_origin()


class AnswerExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = [
            'answerset',
            'question',
            'valid',
            'last_validated',
        ]


class AnswerSetExportSerializer(serializers.ModelSerializer):

    class Meta:
        model = AnswerSet
        fields = [
            'id',
            'identifier',
            'section',
            'parent',
            'data',
            'previous_data',
            'valid',
            'last_validated',
        ]


class PlanExportSerializer(serializers.ModelSerializer):

    class Meta:
        model = Plan
        fields = [
            'id',
            'uuid',
            'title',
            'abbreviation',
            'version',
            'generated_html',
            'valid',
            'last_validated',
            'doi',
            'locked',
            'published',
        ]


class SingleVersionExportSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)
    metadata = MetadataSerializer()
    plan = PlanExportSerializer()
    answersets = AnswerSetExportSerializer(many=True)
    answers = AnswerExportSerializer(many=True)


def serialize_plan_export(plan_pk, variant=DEFAULT_VARIANT, comment=''):
    plan = Plan.objects.get(pk=plan_pk)
    export_obj = plan.create_export_object(variant, True, comment)
    serialized_obj = SingleVersionExportSerializer(export_obj)
    return serialized_obj
