import io
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as tznow

from rest_framework.parsers import JSONParser

from easydmp.dmpt.export_template import ExportSerializer
from easydmp.dmpt.models import (Template, CannedAnswer, Question, Section,
                                 ExplicitBranch, get_origin)
from easydmp.dmpt.models import TemplateImportMetadata, INPUT_TYPES
from easydmp.eestore.models import EEStoreSource, EEStoreType, EEStoreMount


class TemplateImportError(ValueError):
    pass


def _prep_model_dict(model_dict):
    exclude_fields = ['id', 'pk', 'cloned_from', 'cloned_when']
    for field in exclude_fields:
        model_dict.pop(field, None)
    return model_dict


def _check_missing_input_types(template_dict):
    input_types_needed = template_dict.pop('input_types_in_use')
    missing_input_types = set(input_types_needed) - set(INPUT_TYPES)
    if missing_input_types:
        raise TemplateImportError(
            f'The imported template is incompatible with this EasyDMP installation: '
            'The following input types are missing: {missing_input_types}'
        )


def _check_missing_eestore_types_and_sources(eestore_mounts):
    if not eestore_mounts:
        return
    types = set()
    sources = set()
    for em in eestore_mounts:
        types.add(em['eestore_type'])
        sources.update(em['sources'])
    types_found = set(
        EEStoreType.objects.filter(name__in=types).values_list('name', flat=True)
    )
    sources_found = set()
    for source_str in sources:
        try:
            if EEStoreSource.objects.lookup(source_str):
                sources_found.add(source_str)
        except EEStoreSource.DoesNotExist:
            pass
    missing_types = types - types_found
    if missing_types:
        raise TemplateImportError(
            f'The imported template is incompatible with this EasyDMP installation: '
            'The following eestore types are missing: {missing_types}'
        )

    missing_sources = sources - sources_found
    if missing_sources:
        raise TemplateImportError(
            f'The imported template is incompatible with this EasyDMP installation: '
            'The following eestore sources are missing: {missing_sources}'
        )


def deserialize_template_export(export_json) -> dict:
    stream = io.BytesIO(export_json)
    data = JSONParser().parse(stream)
    if not data:
        raise TemplateImportError("Template export is empty")
    serializer = ExportSerializer(data=data)
    if serializer.is_valid():
        return data
    raise TemplateImportError("Template export is malformed")


def _get_free_title(template_dict, origin):
    title = template_dict.pop('title')
    orig_pk = template_dict['id']
    if not Template.objects.filter(title=title).exists():
        return title
    changed_title1 = f'{title} via {origin}#{orig_pk}'
    if not Template.objects.filter(title=changed_title1).exists():
        return changed_title1
    changed_title2 = f'{changed_title1} at {tznow()}'
    if not Template.objects.filter(title=changed_title2).exists():
        return changed_title2
    return f'{changed_title2}, {uuid4()}'


def _create_imported_template(export_dict, origin, via='CLI'):
    template_dict = export_dict['template']
    title = _get_free_title(template_dict, origin)
    original_template_pk = template_dict.pop('id')
    imported_template = Template.objects.create(
        title=title,
        **_prep_model_dict(template_dict)
    )
    tim = TemplateImportMetadata.objects.create(
        template=imported_template,
        origin=origin,
        original_template_pk=original_template_pk,
        originally_cloned_from=template_dict.get('cloned_from'),
        imported_via=via,
    )
    return tim


# These are just similar enough that might be tempting to turn it all
# into a single clever function run four times..
#
# That way lies madness. Don't.


def _create_imported_sections(export_dict, tim):
    mappings = dict()
    section_list = export_dict['sections']
    mappings['sections'] = dict()
    super_section_map = dict()
    for section_dict in section_list:
        orig_id = section_dict.pop('id')
        section_dict.pop('template')
        orig_super_section_id = section_dict.pop('super_section')
        section = Section.objects.create(
            template=tim.template,
            **_prep_model_dict(section_dict)
        )
        mappings['sections'][orig_id] = section.id
        if orig_super_section_id:
            super_section_map[section.id] = orig_super_section_id
    for section in Section.objects.filter(id__in=super_section_map.keys()):
        orig_super_section_id = super_section_map[section.id]
        section.super_section_id = mappings['sections'][orig_super_section_id]
        section.save()
    return mappings


def _create_imported_questions(export_dict, mappings):
    question_list = export_dict['questions']
    mappings['questions'] = dict()
    for question_dict in question_list:
        orig_id = question_dict.pop('id')
        orig_section_id = question_dict.pop('section')
        question = Question.objects.create(
            section_id=mappings['sections'][orig_section_id],
            **_prep_model_dict(question_dict)
        )
        mappings['questions'][orig_id] = question.id
    return mappings


def _create_imported_explicit_branches(export_dict, mappings):
    explicit_branch_list = export_dict['explicit_branches']
    mappings['explicit_branches'] = dict()
    for explicit_branch_dict in explicit_branch_list:
        orig_id = explicit_branch_dict.pop('id')
        orig_current_question_id = explicit_branch_dict.pop('current_question')
        orig_next_question_id = explicit_branch_dict.pop('next_question', None)
        explicit_branch = ExplicitBranch.objects.create(
            current_question_id=mappings['questions'][orig_current_question_id],
            next_question_id=mappings['questions'].get(orig_next_question_id, None),
            **_prep_model_dict(explicit_branch_dict)
        )
        mappings['explicit_branches'][orig_id] = explicit_branch.id
    return mappings


def _create_imported_canned_answers(export_dict, mappings):
    canned_answer_list = export_dict['canned_answers']
    mappings['canned_answers'] = dict()
    for canned_answer_dict in canned_answer_list:
        orig_id = canned_answer_dict.pop('id')
        orig_question_id = canned_answer_dict.pop('question')
        orig_transition_id = canned_answer_dict.pop('transition')
        canned_answer = CannedAnswer.objects.create(
            question_id=mappings['questions'][orig_question_id],
            transition_id=mappings['explicit_branches'].get(orig_transition_id, None),
            **_prep_model_dict(canned_answer_dict)
        )
        mappings['canned_answers'][orig_id] = canned_answer.id
    return mappings


def _create_imported_eestore_mounts(export_dict, mappings):
    eestore_mount_list = export_dict['eestore_mounts']
    for eestore_mount_dict in eestore_mount_list:
        orig_question_id = eestore_mount_dict['question']
        eestore_type = eestore_mount_dict['eestore_type']
        sources = eestore_mount_dict['sources']
        eestore_mount = EEStoreMount.objects.create(
            question_id=mappings['questions'][orig_question_id],
            eestore_type=EEStoreType.objects.get(name=eestore_type)
        )
        for source in sources:
            eestore_mount.sources.add(EEStoreSource.objects.lookup(source))
    # EEStoreMount doesn't need to leave a mapping due to natural keys


def import_serialized_export(export_dict, origin=''):
    if not export_dict:
        raise TemplateImportError("Template export file was empty, cannot import")

    easydmp_dict = export_dict['easydmp']
    chosen_origin = origin or easydmp_dict.get('origin') or get_origin(origin)
    export_version = easydmp_dict.get('version')
    if export_version < settings.VERSION:
        # warning
        pass
    template_dict = export_dict['template']
    eestore_mounts = export_dict.get('eestore_mounts') or []

    # Check compatibility
    _check_missing_input_types(template_dict)
    _check_missing_eestore_types_and_sources(eestore_mounts)

    with transaction.atomic():
        tim = _create_imported_template(export_dict, chosen_origin)
        mappings = _create_imported_sections(export_dict, tim)
        mappings = _create_imported_questions(export_dict, mappings)
        mappings = _create_imported_explicit_branches(export_dict, mappings)
        mappings = _create_imported_canned_answers(export_dict, mappings)
        _create_imported_eestore_mounts(export_dict, mappings)

        # Finally, store the mappings. JSON, keys are converts to str
        tim.mappings = mappings
        tim.save()
        return tim.template
