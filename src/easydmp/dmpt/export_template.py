from django.conf import settings

from rest_framework import serializers

from easydmp.dmpt.models import (Template, Section, Question, ExplicitBranch,
                                 CannedAnswer, get_origin)
from easydmp.eestore.models import EEStoreMount


__all__ = [
    'ExportSerializer',
    'serialize_template_export',
]


def _get_field_names_as_list(model_class):
    return [f.name for f in model_class._meta.fields]


class EasyDMPSerializer(serializers.Serializer):
    version = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()
    input_types = serializers.ListField(
        child=serializers.SlugField(allow_blank=False),
        allow_empty=False,
        min_length=1,
    )

    def get_version(self, _):
        return settings.VERSION

    def get_origin(self, _):
        return get_origin()


class TemplateExportSerializer(serializers.ModelSerializer):
    input_types_in_use = serializers.ListField(
        child=serializers.SlugField(allow_blank=False),
        allow_empty=False,
        min_length=1,
    )

    class Meta:
        model = Template
        fields = _get_field_names_as_list(model) + ['input_types_in_use']
        read_only_fields = fields


class SectionExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = _get_field_names_as_list(model)
        read_only_fields = fields


class QuestionExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = _get_field_names_as_list(model)
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
        many=False, queryset=Question.objects.all()
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


def serialize_template_export(template_pk):
    template = Template.objects.get(pk=template_pk)
    export_obj = template.create_export_object()
    return ExportSerializer(export_obj)
