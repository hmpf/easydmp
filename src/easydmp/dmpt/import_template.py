import io
from uuid import uuid4
import warnings

from django.conf import settings
from django.db import transaction, DatabaseError
from django.utils.timezone import now as tznow

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from easydmp.lib import strip_model_dict
from easydmp.lib.import_export import deserialize_export, get_free_title_for_importing
from easydmp.dmpt.export_template import ExportSerializer
from easydmp.dmpt.models import (Template, CannedAnswer, Question, Section,
                                 ExplicitBranch, TemplateImportMetadata,
                                 )
from easydmp.lib.import_export import get_origin
from easydmp.eestore.models import EEStoreSource, EEStoreType, EEStoreMount


__all__ = [
    'TemplateImportError',
    'deserialize_template_export',
    'import_serialized_template_export',
]


DEFAULT_VIA = TemplateImportMetadata.DEFAULT_VIA


class TemplateImportError(ValueError):
    pass


class TemplateImportWarning(UserWarning):
    pass


def _check_missing_input_types(template_dict):
    try:
        input_types_needed = template_dict['input_types_in_use']
    except KeyError:
        raise TemplateImportError(
            'The imported template is malformed, the list of input types supported by the origin is missing'
        )
    missing_input_types = set(input_types_needed) - set(Question.INPUT_TYPE_IDS)
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
    return deserialize_export(export_json, ExportSerializer, 'Template', TemplateImportError)


@transaction.atomic
def _create_imported_template(export_dict, origin, via=DEFAULT_VIA):
    via = via if via else DEFAULT_VIA
    template_dict = export_dict['template']
    original_title = template_dict['title']
    title = get_free_title_for_importing(template_dict, origin, Template)
    original_template_pk = template_dict.pop('id')

    # Chcek that this template hasn't already been imported from this origin before
    existing_tim = TemplateImportMetadata.objects.filter(
        origin=origin,
        original_template_pk=original_template_pk
    )
    if existing_tim.exists():
        error_msg = (f'Template "{original_title}" #{original_template_pk} '
                     f'has been imported from "{origin}" before, '
                     'will not re-import')
        raise TemplateImportError(error_msg)
    # Ensure the import is not auto-published
    published = template_dict.pop('published', None)

    # Create template
    imported_template = Template.objects.create(
        title=title,
        **strip_model_dict(template_dict, 'input_types_in_use')
    )
    try:
        tim = TemplateImportMetadata.objects.create(
            template=imported_template,
            origin=origin,
            original_template_pk=original_template_pk,
            originally_cloned_from=template_dict.get('cloned_from'),
            originally_published=published,
            imported_via=via,
        )
    except DatabaseError as e:
        raise TemplateImportError(f'{e} Cannot import')
    return tim


def create_identity_template_mapping(template):
    mappings = {
        'sections': {},
        'questions': {},
        'explicit_branches': {},
        'canned_answers': {},
    }
    for section in template.sections.all():
         mappings['sections'][section.id] = section.id
    questions = template.questions.all()
    for question in questions:
        mappings['questions'][question.id] = question.id
    for explicit_branch in ExplicitBranch.objects.filter(current_question__in=questions):
        mappings['explicit_branches'][explicit_branch.id] = explicit_branch.id
    for canned_answer in CannedAnswer.objects.filter(question__in=questions):
        mappings['canned_answers'][canned_answer.id] = canned_answer.id
    return mappings


# These are just similar enough that might be tempting to turn it all
# into a single clever function run four times..
#
# That way lies madness. Don't.


@transaction.atomic
def _create_imported_sections(export_dict, tim):
    section_list = export_dict['sections']
    if not section_list:
        warnings.warn(TemplateImportWarning('This template lacks sections and questions'))
        return
    mappings = {'sections': {}}
    super_section_map = {}
    for section_dict in section_list:
        orig_id = section_dict.pop('id')
        section_dict.pop('template')
        orig_super_section_id = section_dict.pop('super_section')
        section = Section.objects.create(
            template=tim.template,
            **strip_model_dict(section_dict)
        )
        mappings['sections'][orig_id] = section.id
        if orig_super_section_id:
            super_section_map[section.id] = orig_super_section_id
    for section in Section.objects.filter(id__in=super_section_map.keys()):
        orig_super_section_id = super_section_map[section.id]
        section.super_section_id = mappings['sections'][orig_super_section_id]
        section.save()
    return mappings


@transaction.atomic
def _create_imported_questions(export_dict, mappings):
    question_list = export_dict['questions']
    if not question_list:
        warnings.warn(TemplateImportWarning('This template lacks questions'))
        return
    mappings['questions'] = dict()
    for question_dict in question_list:
        orig_id = question_dict.pop('id')
        orig_section_id = question_dict.pop('section')
        input_type_id = question_dict.pop('input_type')
        question = Question.objects.create(
            section_id=mappings['sections'][orig_section_id],
            input_type_id=input_type_id,
            **strip_model_dict(question_dict)
        )
        mappings['questions'][orig_id] = question.id
    return mappings


@transaction.atomic
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
            **strip_model_dict(explicit_branch_dict)
        )
        mappings['explicit_branches'][orig_id] = explicit_branch.id
    return mappings


@transaction.atomic
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
            **strip_model_dict(canned_answer_dict)
        )
        mappings['canned_answers'][orig_id] = canned_answer.id
    return mappings


@transaction.atomic
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


def clean_serialized_template_export(export_dict):
    if not export_dict:
        raise TemplateImportError("Template export file was empty, cannot import")

    section_keys = set(('easydmp', 'template'))
    missing_section_keys = ', '.join(section_keys.difference(export_dict.keys()))
    if missing_section_keys:
        raise TemplateImportError(
            f'Template export file is malformed, lacking the following section(s): {missing_section_keys}. Cannot import'
        )

    easydmp_dict = export_dict['easydmp']
    field_keys = set(('version', 'origin'))
    missing_field_keys = ', '.join(field_keys.difference(easydmp_dict.keys()))
    if missing_field_keys:
        raise TemplateImportError(
            f'Template export file is malformed, lacking the following field(s): {missing_field_keys}. Cannot import'
        )
    export_version = easydmp_dict.get('version')
    if export_version < settings.VERSION:
        # warning
        pass
    template_dict = export_dict['template']
    eestore_mounts = export_dict.get('eestore_mounts', [])

    # Check compatibility
    _check_missing_input_types(template_dict)
    _check_missing_eestore_types_and_sources(eestore_mounts)

    origin = easydmp_dict.get('origin')
    return origin


def import_serialized_template_export(export_dict, origin='', via=DEFAULT_VIA):
    stored_origin = clean_serialized_template_export(export_dict)
    chosen_origin = origin or stored_origin or get_origin(origin)

    empty_mapping = {
        'sections': {},
        'questions': {},
        'explicit_branches': {},
        'canned_answers': {},
        'eestore_mounts': {},
    }
    with transaction.atomic():
        tim = _create_imported_template(export_dict, chosen_origin, via)
        mappings = _create_imported_sections(export_dict, tim)
        if mappings is None:
            tim.mappings = empty_mapping
            tim.save()
            return tim
        mappings = _create_imported_questions(export_dict, mappings)
        if mappings is None:
            tim.mappings = empty_mapping + mappings
            tim.save()
            return tim
        mappings = _create_imported_explicit_branches(export_dict, mappings)
        mappings = _create_imported_canned_answers(export_dict, mappings)
        _create_imported_eestore_mounts(export_dict, mappings)

        # Finally, store the mappings. JSON, keys are converts to str
        tim.mappings = mappings
        tim.save()
        return tim
