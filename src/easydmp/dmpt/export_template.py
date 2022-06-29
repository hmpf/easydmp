from django.conf import settings

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from easydmp.dmpt.models import (Template, Section, Question, ExplicitBranch,
                                 CannedAnswer)
from easydmp.lib.import_export import get_origin
from easydmp.eestore.models import EEStoreMount


__all__ = [
    'ExportSerializer',
    'serialize_template_export',
]


def _get_field_names_as_list(model_class, *extra_fields):
    model_fields = [f.name for f in model_class._meta.fields]
    if extra_fields:
        return model_fields + list(extra_fields)
    return model_fields


def rdadcs_keys_in_use(template):
    rdadcs_question_links = template.questions.values_list('rdadcsquestionlink__key__path', flat=True)
    rdadcs_section_links = template.sections.values_list('rdadcssectionlink__key__path', flat=True)
    used = set(rdadcs_section_links) | set(rdadcs_question_links)
    used.remove(None)
    return sorted(used)


class EasyDMPSerializer(serializers.Serializer):
    version = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()
    input_types = serializers.ListField(
        child=serializers.SlugField(allow_blank=False),
        allow_empty=False,
        min_length=1,
    )

    @extend_schema_field(str)
    def get_version(self, _):
        return settings.VERSION

    @extend_schema_field(str)
    def get_origin(self, _):
        return get_origin()


class TemplateExportSerializer(serializers.ModelSerializer):
    input_types_in_use = serializers.ListField(
        child=serializers.SlugField(allow_blank=False),
        allow_empty=True,
    )
    rdadcs_keys_in_use = serializers.ListField(
        required=False,
        child=serializers.CharField(allow_blank=False),
        allow_empty=True,
    )

    class Meta:
        model = Template
        fields = _get_field_names_as_list(model) + ['input_types_in_use', 'rdadcs_keys_in_use']
        read_only_fields = fields

    def validate(self, attrs):
        # rdadcs is optional
        if 'rdadcs_keys_in_use' not in attrs:
            attrs['rdadcs_keys_in_use'] = []
        return attrs


class SectionExportSerializer(serializers.ModelSerializer):
    rdadcs_path = serializers.CharField(source='rdadcssectionlink.key.path', allow_null=True)

    class Meta:
        model = Section
        fields = _get_field_names_as_list(model, 'rdadcs_path')
        read_only_fields = fields


class QuestionExportSerializer(serializers.ModelSerializer):
    rdadcs_path = serializers.CharField(source='rdadcsquestionlink.key.path', allow_null=True)

    class Meta:
        model = Question
        fields = _get_field_names_as_list(model, 'rdadcs_path')
        read_only_fields = fields


class ExplicitBranchExportSerializer(serializers.ModelSerializer):

    class Meta:
        model = ExplicitBranch
        fields = _get_field_names_as_list(model)
        read_only_fields = fields


class CannedAnswerExportSerializer(serializers.ModelSerializer):

    class Meta:
        model = CannedAnswer
        fields = _get_field_names_as_list(model)
        read_only_fields = fields


class EEStoreMountExportSerializer(serializers.ModelSerializer):
    question = serializers.PrimaryKeyRelatedField(
        many=False, read_only=True,
    )
    eestore_type = serializers.StringRelatedField(many=False, read_only=True)
    sources = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = EEStoreMount
        fields = ['question', 'eestore_type', 'sources']
        read_only_fields = fields


class ExportSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)
    easydmp = EasyDMPSerializer()
    template = TemplateExportSerializer()
    sections = SectionExportSerializer(many=True)
    questions = QuestionExportSerializer(many=True)
    explicit_branches = ExplicitBranchExportSerializer(many=True)
    canned_answers = CannedAnswerExportSerializer(many=True)
    eestore_mounts = EEStoreMountExportSerializer(many=True)


def create_template_export_obj(template):
    template.rdadcs_keys_in_use = rdadcs_keys_in_use(template)
    export_obj = template.create_export_object()
    return export_obj


def serialize_template_export(template_pk):
    template = (
        Template.objects
        .prefetch_related(
            'sections__rdadcssectionlink__key',
            'sections__questions__rdadcsquestionlink__key',
        )
        .get(pk=template_pk)
    )
    export_obj = create_template_export_obj(template)
    return ExportSerializer(export_obj)
