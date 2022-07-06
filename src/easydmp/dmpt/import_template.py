from collections import defaultdict, OrderedDict
from operator import itemgetter
import warnings

from django.conf import settings
from django.db import transaction, DatabaseError

from easydmp.lib import strip_model_dict
from easydmp.lib.import_export import deserialize_export
from easydmp.lib.import_export import get_free_title_for_importing
from easydmp.lib.import_export import DataImportError
from easydmp.dmpt.export_template import ExportSerializer
from easydmp.dmpt.models import (Template, CannedAnswer, Question, Section,
                                 ExplicitBranch, TemplateImportMetadata,
                                 )
from easydmp.lib.import_export import get_origin, DataImportError
from easydmp.eestore.models import EEStoreSource, EEStoreType, EEStoreMount
from easydmp.rdadcs.models import RDADCSKey, RDADCSSectionLink, RDADCSQuestionLink


__all__ = [
    'TemplateImportError',
    'deserialize_template_export',
    'import_serialized_template_export',
]


DEFAULT_VIA = TemplateImportMetadata.DEFAULT_VIA


def get_fieldnames_on_model(model):
    fields = model._meta.get_fields()
    names = set(field.name for field in fields)
    return names


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


def _check_missing_rdadcs_keys(template_dict):
    rdadcs_keys_needed = set()
    try:
        rdadcs_keys_needed = set(template_dict['rdadcs_keys_in_use'])
    except KeyError:
        msg = 'The template export lacks the "rdadcs_keys_in_use" key'
        warnings.warn(TemplateImportWarning(msg))
        return
    rdadcs_keys = set(RDADCSKey.objects.values_list('path', flat=True))
    missing_rdadcs_keys = rdadcs_keys_needed - rdadcs_keys
    if missing_rdadcs_keys:
        raise TemplateImportError(
            'The imported template is incompatible with this EasyDMP installation: '
            f'The following RDADCS keys are missing: {missing_rdadcs_keys}'
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


def get_template_id(export_dict):
    try:
        return export_dict['template']['id']
    except KeyError:
        raise TemplateImportError(
            'Template export file is malformed, there should be a "template" '
            'section with an "id" key. Cannot import'
        )


def get_template_and_mappings(export_dict=None, template_id=None, origin='', via=DEFAULT_VIA):
    """Get or create template and mappings

    If not export_dict, try returning the template in the template id and an
    identity mapping. If both export_dict and template_id, check that the id
    in the export_dict is the same as the template_id.
    """

    assert export_dict or template_id

    origin = get_origin(origin)
    stored_origin = None
    if export_dict:
        external_template_id = template_id
        stored_origin = get_stored_template_origin(export_dict)
        template_id = get_template_id(export_dict)
        if external_template_id and (external_template_id != template_id):
            error_msg = ('The export is malformed, the id for the '
                         'included template does not match the id given. '
                         'Aborting import.')
            raise TemplateImportError(error_msg)

    # Check if this is a local template: id exists, and origin is the same
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

    tim = import_or_get_template(export_dict, origin='', via=DEFAULT_VIA)
    return tim.template, tim.mappings


def import_or_get_template(export_dict, origin='', via=DEFAULT_VIA):
    """Import a new template or connect an external template"""
    clean_serialized_template_export(export_dict)
    # override origin if given
    origin = origin or get_stored_template_origin(export_dict)
    template_id = get_template_id(export_dict)

    # Check if this template already exists with this uuid
    uuid = export_dict['template'].get('uuid', None)
    if uuid:
        try:
            template = Template.objects.get(uuid=uuid)
        except Template.DoesNotExist:
            # Unknown template, we'll import it the normal way
            pass
        else:
            # Check if this is a previously imported template
            try:
                tim = TemplateImportMetadata.objects.get(template=template)
            except TemplateImportMetadata.DoesNotExist:
                # create the new mappings without creating a new template
                tim = connect_template_import_to_existing_template(
                    template,
                    export_dict,
                    origin,
                    via,
                )
            return tim

    # Check if this is a previously imported template
    try:
        tim = TemplateImportMetadata.objects.get(origin=origin, original_template_pk=template_id)
    except TemplateImportMetadata.DoesNotExist:
        # import the template
        tim = import_serialized_template_export(export_dict, origin, via)

    return tim


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
    cloned_from = template_dict.get('cloned_from', None)

    # Ensure the import is not auto-published
    published = template_dict.pop('published', None)

    # Prep what keys, values to copy over
    stripped_dict = strip_model_dict(template_dict, 'input_types_in_use',
                                    'rdadcs_keys_in_use')
    # remove fields that do not exist in this version of the Template model
    fieldnames = get_fieldnames_on_model(Template).intersection(stripped_dict)
    creation_dict = {key: stripped_dict[key] for key in fieldnames}
    # Create template
    imported_template = Template.objects.create(title=title, **creation_dict)
    tim = _create_template_import_metadata(imported_template, origin, original_template_pk, published, cloned_from, via)
    return tim


def _create_template_import_metadata(template, origin, original_pk, original_published=None, original_cloned_from=None, via=DEFAULT_VIA):
    try:
        tim = TemplateImportMetadata.objects.create(
            template=template,
            origin=origin,
            original_template_pk=original_pk,
            originally_cloned_from=original_cloned_from,
            originally_published=original_published,
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
# into a single clever function..
#
# That way lies madness. Don't.


@transaction.atomic
def _create_imported_sections(export_dict, tim):
    section_list = export_dict['sections']
    if not section_list:
        warnings.warn(TemplateImportWarning('This template lacks sections and questions'))
        return
    mappings = {'sections': {}}

    order_map, super_section_map, orig_identifier_question_map, rdadcs_paths = _get_imported_section_ordering(section_list)
    mappings['rdadcs_sections'] = rdadcs_paths

    # sections link to other sections, important to
    # create sections in the correct order
    identifier_question_set = set()
    section_map = {}
    for depth in order_map:
        section_list = []
        for section_dict in order_map[depth]:
            orig_id = section_dict['id']
            section_dict.pop('template')
            stripped_dict = strip_model_dict(section_dict, 'super_section')
            section = Section(template=tim.template, **stripped_dict)
            # Wanted to use bulk_create but primary keys are not returned..
            section.save(do_section_question=False)
            section_map[orig_id] = section.id
    for orig_id, new_id in section_map.items():
        orig_identifier_question_id = orig_identifier_question_map.get(orig_id, None)
        if orig_identifier_question_id:
            identifier_question_set.add(orig_identifier_question_id)
        orig_super_section_id = super_section_map[orig_id]
        if orig_super_section_id:  # top level sections lack a super_section
            new_super_section = section_map[orig_super_section_id]
            section.super_section_id = new_super_section
            section.save(do_section_question=False)

    mappings['identifier_questions'] = identifier_question_set
    mappings['sections'] = section_map
    return mappings


def _map_imported_sections(export_dict, tim):
    section_list = export_dict['sections']
    mappings = {'sections': {}}
    template = tim.template
    order_map, _, _, _ = _get_imported_section_ordering(section_list)

    # get the existing scetion in the same format as the imported ones
    existing_sections = template.sections.order_by('section_depth', 'super_section', 'position')
    existing_order_map = defaultdict(list)
    for section_dict in existing_sections.values('super_section', 'position', 'section_depth', 'id'):
        depth = section_dict['section_depth']
        existing_order_map[int(depth)].append(section_dict)

    for depth, section_dicts in existing_order_map.items():
        section_dicts = sorted(section_dicts, key=itemgetter('super_section', 'position'))
        existing_order_map[depth] = section_dicts

    # compare and create the map
    section_map = dict()
    for depth in order_map:
        imported_ids = [section_dict['id'] for section_dict in order_map[depth]]
        existing_ids = [section_dict['id'] for section_dict in existing_order_map[depth]]
        section_map.update(zip(existing_ids,imported_ids))
    mappings['sections'] = section_map
    return mappings


def _get_imported_section_ordering(section_list):
    # build maps to create Sections in the correct order
    super_section_map = {}
    order_map = defaultdict(list)
    orig_identifier_question_map = {}
    rdadcs_paths = {}
    for section_dict in section_list:
        orig_id = section_dict['id']

        orig_super_section_id = section_dict['super_section']
        super_section_map[orig_id] = orig_super_section_id

        orig_identifier_question_id = section_dict.pop('identifier_question', None)
        if orig_identifier_question_id:
            orig_identifier_question_map[orig_id] = orig_identifier_question_id

        rdadcs_paths[orig_id] = section_dict.pop('rdadcs_path', None)

        depth = section_dict['section_depth']
        order_map[int(depth)].append(section_dict)

    # order by super_section and position
    for depth, section_dicts in order_map.items():
        section_dicts = sorted(section_dicts, key=itemgetter('super_section', 'position'))
        order_map[depth] = section_dicts

    # ensure the keys are in increasing order
    order_map = OrderedDict(sorted(order_map.items()))
    return order_map, super_section_map, orig_identifier_question_map, rdadcs_paths


@transaction.atomic
def _create_imported_questions(export_dict, mappings):
    question_list = export_dict['questions']
    if not question_list:
        warnings.warn(TemplateImportWarning('This template lacks questions'))
        return
    mappings['questions'] = dict()
    orig_order = defaultdict(list)
    questions_by_section = defaultdict(list)

    rdadcs_paths = {}
    # Order per section
    for question_dict in question_list:
        orig_id = question_dict.pop('id')
        rdadcs_paths[orig_id] = question_dict.pop('rdadcs_path', None)
        orig_section_id = question_dict.pop('section')
        new_section_id = mappings['sections'][orig_section_id]
        question = Question(
            section_id=new_section_id,
            input_type_id=question_dict.pop('input_type'),
            **strip_model_dict(question_dict)
        )
        question.save()
        mappings['questions'][orig_id] = question.id
        identifies_section = orig_id in mappings['identifier_questions']
        if identifies_section:
            question.section.identifier_question = question
            question.section.save(do_section_question=False)
    del mappings['identifier_questions']
    mappings['rdadcs_questions'] = rdadcs_paths
    return mappings


def _map_imported_questions(export_dict, mappings):
    question_list = export_dict['questions']
    mappings['questions'] = dict()
    orig_order = defaultdict(dict)
    # Order per section
    for question_dict in question_list:
        orig_id = question_dict.pop('id')
        orig_section_id = question_dict.pop('section')
        position = question_dict['position']
        orig_order[orig_section_id][position] = orig_id
    new_order = defaultdict(dict)
    for question in Question.objects.all():
        new_order[question.section_id][question.position] = question.id
    for orig_section_id, questions in orig_order.items():
        new_section_id = mappings['sections'][orig_section_id]
        for position, question_id in questions.items():
            new_id = new_order[new_section_id][position]
            mappings['questions'][question_id] = new_id

    return mappings


@transaction.atomic
def _create_rdadcs_links(mappings):
    keymap = {key.path: key.slug for key in RDADCSKey.objects.all()}

    section_paths = mappings.pop('rdadcs_sections', {})
    if section_paths:
        section_key_list = []
        for pk, path in section_paths.items():
            if not path: continue
            key = keymap[path]
            section_id = mappings['sections'][pk]
            section_key_list.append(
                RDADCSSectionLink(key_id=key, section_id=section_id)
            )
        RDADCSSectionLink.objects.bulk_create(section_key_list)

    question_paths = mappings.pop('rdadcs_questions', {})
    if question_paths:
        question_key_list = []
        for pk, path in question_paths.items():
            if not path: continue
            key = keymap[path]
            question_id = mappings['questions'][pk]
            question_key_list.append(
                RDADCSQuestionLink(key_id=key, question_id=question_id)
            )
        RDADCSQuestionLink.objects.bulk_create(question_key_list)


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
def _map_imported_explicit_branches(export_dict, mappings):
    explicit_branch_list = export_dict['explicit_branches']
    mappings['explicit_branches'] = dict()
    for explicit_branch_dict in explicit_branch_list:
        orig_id = explicit_branch_dict.pop('id')
        orig_current_question_id = explicit_branch_dict.pop('current_question')
        orig_next_question_id = explicit_branch_dict.pop('next_question', None)
        new_current_question_id = mappings['questions'][orig_current_question_id]
        new_next_question_id = mappings['questions'].get(orig_next_question_id, None)
        new_explicit_branch = ExplicitBranch.objects.get(
            current_question_id=new_current_question_id,
            next_question_id=new_next_question_id,
            category=explicit_branch_dict['category'],
            condition=explicit_branch_dict['condition'],
        )
        mappings['explicit_branches'][orig_id] = new_explicit_branch.id
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
def _map_imported_canned_answers(export_dict, mappings):
    canned_answer_list = export_dict['canned_answers']
    mappings['canned_answers'] = dict()
    for canned_answer_dict in canned_answer_list:
        orig_id = canned_answer_dict.pop('id')
        orig_question_id = canned_answer_dict.pop('question')
        orig_transition_id = canned_answer_dict.pop('transition')
        new_question_id = mappings['questions'][orig_question_id]
        new_transition_id = mappings['explicit_branches'].get(orig_transition_id, None)
        canned_answers = CannedAnswer.objects.filter(
            question_id=new_question_id,
            transition_id=new_transition_id,
        )
        for ca in canned_answers:
            mappings['canned_answers'][orig_id] = ca.id
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
    get_template_id(export_dict)

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
    _check_missing_rdadcs_keys(template_dict)
    _check_missing_eestore_types_and_sources(eestore_mounts)


def connect_template_import_to_existing_template(template, export_dict, origin='', via=DEFAULT_VIA):
    clean_serialized_template_export(export_dict)
    stored_origin = get_stored_template_origin(export_dict)
    chosen_origin = origin or stored_origin or get_origin(origin)
    original_pk = export_dict['template'].pop('id')
    cloned_from = export_dict['template'].get('cloned_from', None)
    published = export_dict['template'].pop('published', None)

    empty_mapping = {
        'sections': {},
        'questions': {},
        'explicit_branches': {},
        'canned_answers': {},
        'eestore_mounts': {},
    }
    with transaction.atomic():
        tim = _create_template_import_metadata(template, chosen_origin, original_pk, published, cloned_from, via)
        mappings = _map_imported_sections(export_dict, tim)
        if mappings is None:
            tim.mappings = empty_mapping
            tim.save()
            return tim
        mappings = _map_imported_questions(export_dict, mappings)
        if mappings is None:
            tim.mappings = empty_mapping
            tim.save()
            return tim
        mappings = _map_imported_explicit_branches(export_dict, mappings)
        mappings = _map_imported_canned_answers(export_dict, mappings)

        # Finally, store the mappings. JSON, keys are converts to str
        tim.mappings = mappings
        tim.save()
        return tim


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
        _create_rdadcs_links(mappings)

        # Finally, store the mappings. JSON, keys are converts to str
        tim.mappings = mappings
        tim.save()
        return tim
