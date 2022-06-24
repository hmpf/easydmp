from collections import defaultdict
from operator import itemgetter
import warnings

from django.conf import settings
from django.db import transaction, DatabaseError

from easydmp.lib import strip_model_dict
from easydmp.lib.import_export import deserialize_export, get_free_title_for_importing, DataImportError
from easydmp.dmpt.export_template import ExportSerializer
from easydmp.dmpt.models import (Template, CannedAnswer, Question, Section,
                                 ExplicitBranch, TemplateImportMetadata,
                                 )
from easydmp.lib.import_export import get_origin, DataImportError
from easydmp.eestore.models import EEStoreSource, EEStoreType, EEStoreMount


__all__ = [
    'TemplateImportError',
    'deserialize_template_export',
    'import_serialized_template_export',
]


DEFAULT_VIA = TemplateImportMetadata.DEFAULT_VIA


class TemplateImportError(DataImportError):
    pass


class TemplateImportAlreadyExistsError(TemplateImportError):
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
            'The imported template is incompatible with this EasyDMP installation: '
            f'The following input types are missing: {missing_input_types}'
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
            'The imported template is incompatible with this EasyDMP installation: '
            f'The following eestore types are missing: {missing_types}'
        )

    missing_sources = sources - sources_found
    if missing_sources:
        raise TemplateImportError(
            'The imported template is incompatible with this EasyDMP installation: '
            f'The following eestore sources are missing: {missing_sources}'
        )


def get_stored_template_origin(export_dict):
    try:
        return export_dict['easydmp']['origin']
    except KeyError:
        raise TemplateImportError(
            'Template export file is malformed, there should be an "easydmp" '
            'section with an "origin" key. Cannot import'
        )


def get_template_and_mappings(export_dict=None, template_id=None, origin='', via=DEFAULT_VIA):
    "Get or create template and mappings"
    assert export_dict or template_id

    origin = get_origin(origin)
    stored_origin = None
    if export_dict:
        external_template_id = template_id
        clean_serialized_template_export(export_dict)
        stored_origin = get_stored_template_origin(export_dict)
        template_id = export_dict['template']['id']
        if external_template_id and (external_template_id != template_id):
            error_msg = ('The export is malformed, the id for the '
                         'included template does not match the id given. '
                         'Aborting import.')
            raise TemplateImportError(error_msg)

    # Check if this is a local template
    if not stored_origin or stored_origin == origin:
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            raise TemplateImportError(
                'The template for this plan ought to already exist but might '
                'have been deleted.'
            )
        else:
            mappings = create_identity_template_mapping(template)
            return template, mappings

    template_dict = export_dict['template']

    # Check if this is a previously imported template
    try:
        tim = TemplateImportMetadata.objects.get(origin=stored_origin, original_template_pk=template_id)
    except TemplateImportMetadata.DoesNotExist:
        # import the template
        tim = import_serialized_template_export(export_dict, stored_origin, via)

    return tim.template, tim.mappings


def deserialize_template_export(export_json) -> dict:
    return deserialize_export(export_json, ExportSerializer, 'Template', TemplateImportError)


def ensure_unknown_template(export_dict, origin):
    # Chcek that this template hasn't already been imported from this origin before
    template_dict = export_dict['template']
    original_template_pk = template_dict['id']
    existing_tim = TemplateImportMetadata.objects.filter(
        origin=origin,
        original_template_pk=original_template_pk
    )
    if existing_tim.exists():
        error_msg = (f'''Template "{template_dict['title']}" '''
                     f'#{original_template_pk} has been imported from '
                     f'"{origin}" before, will not re-import')
        raise TemplateImportAlreadyExistsError(error_msg)


@transaction.atomic
def _create_imported_template(export_dict, origin, via=DEFAULT_VIA):
    via = via if via else DEFAULT_VIA
    template_dict = export_dict['template']
    title = get_free_title_for_importing(template_dict, origin, Template)
    original_template_pk = template_dict.pop('id')

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

    # build maps to create Sections in the correct order
    super_section_map = {}
    order_map = defaultdict(list)
    orig_identifier_question_map = {}
    for section_dict in section_list:
        orig_id = section_dict['id']

        orig_super_section_id = section_dict['super_section']
        super_section_map[orig_id] = orig_super_section_id

        orig_identifier_question_id = section_dict.pop('identifier_question')
        orig_identifier_question_map[orig_id] = orig_identifier_question_id

        depth = section_dict['section_depth']
        order_map[int(depth)].append(section_dict)

    # order by super_section and position
    for depth, section_dicts in order_map.items():
        section_dicts = sorted(section_dicts, key=itemgetter('super_section', 'position'))
        order_map[depth] = section_dicts

    # create sections in the correct order
    identifier_question_set = set()
    section_map = {}
    for depth in sorted(order_map):
        section_list = []
        for section_dict in order_map[depth]:
            section_dict.pop('template')
            stripped_dict = strip_model_dict(section_dict, 'super_section')
            section = Section(template=tim.template, **stripped_dict)
            section_list.append(section)
        new_section_list = Section.objects.bulk_create(section_list)
        for i, section in enumerate(new_section_list):
            orig_id = order_map[depth][i]['id']
            orig_identifier_question_id = orig_identifier_question_map[orig_id]
            identifier_question_set.add(orig_identifier_question_id)
            section_map[orig_id] = section
    mappings['identifier_questions'] = identifier_question_set

    # set super_section and section mappings
    for orig_id, section in section_map.items():
        orig_super_section_id = super_section_map[orig_id]
        if orig_super_section_id:  # top level sections lack a super_section
            new_super_section = section_map[orig_super_section_id]
            section.super_section = new_super_section
            section.save(do_section_question=False)
        mappings['sections'][orig_id] = section.id

    return mappings


@transaction.atomic
def _create_imported_questions(export_dict, mappings):
    question_list = export_dict['questions']
    if not question_list:
        warnings.warn(TemplateImportWarning('This template lacks questions'))
        return
    mappings['questions'] = dict()
    orig_order = defaultdict(list)
    questions_by_section = defaultdict(list)

    # Order per section
    for question_dict in question_list:
        orig_id = question_dict.pop('id')
        orig_section_id = question_dict.pop('section')
        new_section_id = mappings['sections'][orig_section_id]
        question = Question(
            section_id=mappings['sections'][orig_section_id],
            input_type_id=question_dict.pop('input_type'),
            **strip_model_dict(question_dict)
        )
        orig_order[orig_section_id].append(orig_id)
        questions_by_section[orig_section_id].append(question)
    for orig_section_id, questions in questions_by_section.items():
        new_questions = Question.objects.bulk_create(questions)
        for i, question in enumerate(new_questions):
            orig_id = orig_order[orig_section_id][i]
            mappings['questions'][orig_id] = question.id
            identifies_section = orig_id in mappings['identifier_questions']
            if identifies_section:
                question.section.identifier_question = question
                question.section.save()
    del mappings['identifier_questions']
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


def import_serialized_template_export(export_dict, origin='', via=DEFAULT_VIA):
    clean_serialized_template_export(export_dict)
    stored_origin = get_stored_template_origin(export_dict)
    chosen_origin = origin or stored_origin or get_origin(origin)
    ensure_unknown_template(export_dict, chosen_origin)

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
            tim.mappings = empty_mapping
            tim.save()
            return tim
        mappings = _create_imported_explicit_branches(export_dict, mappings)
        mappings = _create_imported_canned_answers(export_dict, mappings)
        _create_imported_eestore_mounts(export_dict, mappings)

        # Finally, store the mappings. JSON, keys are converts to str
        tim.mappings = mappings
        tim.save()
        return tim
