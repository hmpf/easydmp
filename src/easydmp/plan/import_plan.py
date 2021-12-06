from collections import namedtuple
import logging
import warnings

from django.contrib.auth import get_user_model
from django.db import transaction, DatabaseError

from easydmp.dmpt.import_template import clean_serialized_template_export
from easydmp.dmpt.import_template import import_serialized_template_export
from easydmp.dmpt.import_template import create_identity_template_mapping
from easydmp.dmpt.import_template import TemplateImportError
from easydmp.dmpt.models import Template, TemplateImportMetadata
from easydmp.dmpt.utils import get_origin
from easydmp.eventlog.utils import log_event
from easydmp.lib import get_free_title_for_importing, deserialize_export, strip_model_dict

from .export_plan import SingleVersionExportSerializer
from .models import Plan, PlanImportMetadata, AnswerSet, Answer


__all__ = [
    'PlanImportError',
    'deserialize_plan_export',
    'import_serialized_plan_export',
]


DEFAULT_VIA = TemplateImportMetadata.DEFAULT_VIA
LOG = logging.getLogger(__name__)
User = get_user_model()


PreliminaryPlanImportMetadata = namedtuple('PreliminaryPlanImportMetadata', ['version', 'origin', 'variant', 'template_id'])


class PlanImportError(ValueError):
    pass


class PlanImportWarning(UserWarning):
    pass


def deserialize_plan_export(export_json) -> dict:
    return deserialize_export(export_json, SingleVersionExportSerializer, 'Plan', PlanImportError)


def get_metadata(export_dict, via=DEFAULT_VIA):
    my_origin = get_origin()
    metadata_dict = export_dict['metadata']
    stored_origin = metadata_dict['origin']
    if stored_origin == my_origin:
        plan_id = export_dict['plan']['id']
        if Plan.objects.filter(id=int(plan_id)).exists():
            error_msg = ('This plan already exists in this origin. '
                         'Make a new version if you want a new copy.')
            raise PlanImportError(error_msg)
    template_id = metadata_dict['template_id']
    template_export_dict = metadata_dict['template_copy']
    mappings = {}
    if template_export_dict:
        with transaction.atomic():
            if not template_export_dict['template']['id'] == template_id:
                error_msg = ('The export is malformed, the id for the '
                             'included template does not match the id in the '
                             'metadata. Aborting import.')
                raise PlanImportError(error_msg)
            template, mappings, template_origin = get_template_import_metadata(template_export_dict, my_origin)
            if stored_origin != template_origin:
                error_msg = ('The export is malformed, the origin for the '
                             'included template does not match the origin in '
                             'the metadata. Aborting import.')
                raise PlanImportError(error_msg)
    else:
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            error_msg = ('The template is not included in the export but'
                         'does not exist locally already. Cannot import.')
            raise PlanImportError(error_msg)
    if not mappings:
        mappings = create_identity_template_mapping(template)
    metadata = PreliminaryPlanImportMetadata(metadata_dict['version'], metadata_dict['origin'], metadata_dict['variant'], template_id)
    return template, mappings, metadata


def get_template_import_metadata(template_export_dict, origin, via=DEFAULT_VIA):
    stored_origin = clean_serialized_template_export(template_export_dict)
    template_dict = template_export_dict['template']
    template_id = template_dict['id']

    easydmp_dict = template_export_dict['easydmp']
    version = easydmp_dict['version']
    # Check if this is a local template
    if stored_origin == origin:
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            raise PlanImportError('The template for this plan ought to already '
                                  'exist but might have been deleted. '
                                  'Import the template manually first.')
        else:
            return template, None, stored_origin

    # Check if this is a previously imported template
    try:
        tim = TemplateImportMetadata.objects.get(origin=stored_origin, original_template_pk=template_id)
    except TemplateImportMetadata.DoesNotExist:
        # import the template
        tim = import_serialized_template_export(template_export_dict, stored_origin, via)

    return tim.template, tim.mappings, tim.origin


def _map_data_to_new_keys(data, mapping):
    remapped_data = {}
    for key, value in data.items():
        new_key = str(mapping[int(key)])
        remapped_data[new_key] = value
    return remapped_data


@transaction.atomic
def _create_imported_plan(user, template, export_dict, metadata, via=DEFAULT_VIA):
    via = via if via else DEFAULT_VIA

    plan_dict = export_dict['plan']
    original_title = plan_dict['title']
    title = get_free_title_for_importing(plan_dict, metadata.origin, Plan)
    original_plan_pk = plan_dict.pop('id')
    original_template_pk = metadata.template_id

    # Chcek that this plan hasn't already been imported from this origin before
    existing_pim = PlanImportMetadata.objects.filter(
        origin=metadata.origin,
        original_plan_pk=original_plan_pk,
        original_template_pk=original_template_pk,
    )
    if existing_pim.exists():
        error_msg = (f'Plan "{original_title}" #{original_plan_pk} has been '
                     f'imported from "{metadata.origin}" before, '
                     'will not re-import')
        raise PlanImportError(error_msg)

    # Ensure the import is not auto-published
    published = plan_dict.pop('published', None)
    locked = plan_dict.pop('locked', None)

    # Create plan
    imported_plan = Plan(
        added_by=user,
        modified_by=user,
        template=template,
        title=title,
        **strip_model_dict(plan_dict, 'added_by', 'modified_by')
    )
    imported_plan.save(importing=True)
    try:
        pim = PlanImportMetadata.objects.create(
            plan=imported_plan,
            origin=metadata.origin,
            original_plan_pk=original_plan_pk,
            original_template_pk=original_template_pk,
            originally_cloned_from=plan_dict.get('cloned_from'),
            originally_locked=locked,
            originally_published=published,
            variant=metadata.variant,
            imported_via=via,
        )
    except DatabaseError as e:
        raise PlanImportError(f'{e} Cannot import')
    return pim


@transaction.atomic
def _create_answersets(export_dict, pim, mappings):
    answerset_list = export_dict['answersets']
    if not answerset_list:
        warnings.warn(PlanImportWarning('This plan is empty as it lacks answers'))
        return
    mappings['answersets'] = {}
    parent_map = {}
    sections_visited = set()
    for answerset_dict in answerset_list:
        orig_id = answerset_dict.pop('id')
        orig_parent_id = answerset_dict.pop('parent')
        orig_section_id = answerset_dict.pop('section')
        orig_data = answerset_dict.pop('data')
        data = _map_data_to_new_keys(orig_data, mappings['questions'])
        orig_previous_data = answerset_dict.pop('previous_data')
        previous_data = _map_data_to_new_keys(orig_previous_data, mappings['questions'])
        answerset = AnswerSet(
            plan=pim.plan,
            section_id=mappings['sections'][orig_section_id],
            data=data,
            previous_data=previous_data,
            **strip_model_dict(answerset_dict),
        )
        answerset.save(importing=True)
        sections_visited.add(answerset.section)
        mappings['answersets'][orig_id] = answerset.id
        if orig_parent_id:
            parent_map[answerset.id] = orig_parent_id
    # Set parents
    for answerset in AnswerSet.objects.filter(plan=pim.plan, id__in=parent_map.keys()):
        orig_parent_id = parent_map[answerset.id]
        answerset.parent_id = mappings['answersets'][orig_parent_id]
        answerset.save()
    # Set visited_sections
    pim.plan.visited_sections.set(sections_visited)


@transaction.atomic
def _create_answers(export_dict, pim, mappings):
    answer_list = export_dict['answers']
    if not answer_list:
        warnings.warn(PlanImportWarning('This plan lacks answers'))
        return
    for answer_dict in answer_list:
        #breakpoint()
        orig_answerset_id = answer_dict.pop('answerset')
        orig_question_id = answer_dict.pop('question')
        answer = Answer.objects.create(
            answerset_id=mappings['answersets'][orig_answerset_id],
            question_id=mappings['questions'][orig_question_id],
            **strip_model_dict(answer_dict),
        )


def import_serialized_plan_export(export_dict, user, via=DEFAULT_VIA):
    if not export_dict:
        raise PlanImportError("Plan export file was empty, cannot import")

    with transaction.atomic():
        try:
            template, mapping, metadata = get_metadata(export_dict, via)
        except PlanImportError:
            raise
        except TemplateImportError as tie:
            raise PlanImportError(f'Cannot import plan: {tie}')

        pim = _create_imported_plan(user, template, export_dict, metadata, via)
        plan = pim.plan
        _create_answersets(export_dict, pim, mapping)
        _create_answers(export_dict, pim, mapping)
#         log_template = '{timestamp} {actor} imported {target}' + f' via {via}'
#         log_event(plan.added_by, 'import', target=plan,
#                   timestamp=imported_plan.added, template=log_template)
#     LOG.info('Imported plan "%s" (%i) via {via}', plan, plan.pk)
    return pim
