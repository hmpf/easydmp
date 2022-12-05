from collections import namedtuple
import logging
import warnings

from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction, DatabaseError, models

from easydmp.dmpt.import_template import TemplateImportError
from easydmp.dmpt.import_template import get_template_and_mappings
from easydmp.dmpt.import_template import get_stored_template_origin
from easydmp.dmpt.models import TemplateImportMetadata
from easydmp.eventlog.utils import log_event
from easydmp.lib import strip_model_dict
from easydmp.lib.import_export import PlanImportError
from easydmp.lib.import_export import deserialize_export
from easydmp.lib.import_export import get_free_title_for_importing
from easydmp.lib.import_export import get_origin
from easydmp.lib.import_export import load_json_from_stream
from easydmp.rdadcs.lib.import_plan import ImportRDA11

from .export_plan import SingleVersionExportSerializer
from .models import Plan, PlanImportMetadata, AnswerSet, Answer


__all__ = [
    'PlanImportError',
    'PlanExportType',
    'detect_export_type',
    'deserialize_plan_export',
    'import_serialized_plan_export',
]


DEFAULT_VIA = TemplateImportMetadata.DEFAULT_VIA
LOG = logging.getLogger(__name__)
User = get_user_model()


PreliminaryPlanImportMetadata = namedtuple(
    'PreliminaryPlanImportMetadata',
    ['version', 'origin', 'variant', 'template_id']
)


class PlanImportWarning(UserWarning):
    pass


class PlanExportType(models.TextChoices):
    EASYDMP = 'EASYDMP', "EasyDMP"
    RDADCS = 'RDADCS', "RDADCS"


def detect_export_type(export_json) -> PlanExportType:
    data = load_json_from_stream(export_json, 'Plan', PlanImportError)
    if set(data.keys()) >= set(('plan', 'answersets', 'comment', 'metadata')):
        # EasyDMP
        return PlanExportType.EASYDMP
    elif 'dmp' in data:
        # RDA DMP CS
        return PlanExportType.RDADCS
    raise PlanImportError('Unknown export format')


def deserialize_plan_export(export_json) -> dict:
    return deserialize_export(export_json, SingleVersionExportSerializer, 'Plan', PlanImportError)


def ensure_unknown_plan(export_dict, origin):
    # Chcek that this plan hasn't already been imported from this origin before
    plan_dict = export_dict['plan']
    original_plan_pk = plan_dict['id']
    existing_pim = PlanImportMetadata.objects.filter(
        origin=origin,
        original_plan_pk=original_plan_pk
    )
    if existing_pim.exists():
        error_msg = (f'''Plan "{plan_dict['title']}" '''
                     f'#{original_plan_pk} has been imported from '
                     f'"{origin}" before, will not re-import')
        raise PlanImportError(error_msg)


def get_stored_plan_origin(export_dict):
    try:
        return export_dict['metadata']['origin']
    except KeyError:
        raise PlanImportError(
            'Plan export file is malformed, there should be a "metadata" '
            'section with an "origin" key. Cannot import'
        )


def build_metadata(export_dict, origin='', via=DEFAULT_VIA):
    origin = get_origin(origin)
    metadata_dict = export_dict['metadata']
    stored_origin = get_stored_plan_origin(export_dict)
    if stored_origin == origin:
        plan_id = export_dict['plan']['id']
        if Plan.objects.filter(id=int(plan_id)).exists():
            error_msg = ('This plan already exists in this origin. '
                         'Make a new version if you want a new copy.')
            raise PlanImportError(error_msg)
    template_id = metadata_dict['template_id']
    metadata = PreliminaryPlanImportMetadata(metadata_dict['version'], metadata_dict['origin'], metadata_dict['variant'], template_id)
    return metadata


def get_template_metadata(metadata_dict):
    template_id = metadata_dict['template_id']
    export_dict = metadata_dict['template_copy']
    if export_dict:
        template_origin = get_stored_template_origin(export_dict)
        stored_origin = metadata_dict['origin']
        if stored_origin != template_origin:
            error_msg = ('The export is malformed, the origin for the '
                         'included template does not match the origin in '
                         'the metadata. Aborting import.')
            raise PlanImportError(error_msg)
        return template_id, export_dict
    else:
        return template_id, {}


def _map_data_to_new_keys(data, mapping):
    remapped_data = {}
    for key, value in data.items():
        new_key = mapping.get(int(key), None)
        if new_key:
            remapped_data[str(new_key)] = value
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


def import_serialized_plan_export(export_dict, user, via=DEFAULT_VIA):
    if not export_dict:
        raise PlanImportError("Plan export file was empty, cannot import")

    with transaction.atomic():
        try:
            metadata = build_metadata(export_dict, via)
        except PlanImportError:
            raise
        except TemplateImportError as tie:
            raise PlanImportError(f'Cannot import plan: {tie}')
        ensure_unknown_plan(export_dict, metadata.origin)

        try:
            metadata_dict = export_dict['metadata']
            template_id, template_copy = get_template_metadata(metadata_dict)
        except PlanImportError:
            raise
        template, mapping = get_template_and_mappings(
            template_copy,
            template_id,
            metadata.origin,
            via
        )

        pim = _create_imported_plan(user, template, export_dict, metadata, via)
        _create_answersets(export_dict, pim, mapping)
#         plan = pim.plan
#         log_template = '{timestamp} {actor} imported {target}' + f' via {via}'
#         log_event(plan.added_by, 'import', target=plan,
#                   timestamp=imported_plan.added, template=log_template)
#     LOG.info('Imported plan "%s" (%i) via {via}', plan, plan.pk)
    return pim


class PlanImporter:

    def __init__(self, request, via=DEFAULT_VIA):
        self.request = request
        self.via = via
        self.pim = None
        self.msg = None
        self.errors = []
        self.warnings = []

    def import_plan(self):
        plan_export_file = self.request.FILES['plan_export_file']
        plan_export_jsonblob = plan_export_file.read()
        try:
            export_type = detect_export_type(plan_export_jsonblob)
        except PlanImportError as e:
            self.errors.append(str(e))
            return None
        try:
            if export_type == PlanExportType.EASYDMP:
                pim = self.import_easydmp(plan_export_jsonblob)
            elif export_type == PlanExportType.RDADCS:
                pim = self.import_rdadcs(plan_export_jsonblob)
        except PlanImportError as e:
            self.errors.append(str(e))
            return None
        self.msg = f'Plan "{pim.plan}" successfully imported'
        self.pim = pim
        return pim

    def message(self):
        for error in self.errors:
            messages.error(self.request, error)
        for warning in self.warnings:
            messages.warning(self.request, warning)
        if self.msg:
            messages.success(self.request, self.msg)

    def audit_log(self):
        if self.msg and self.pim:
            log_event(self.request.user, 'import', target=self.pim.plan,
                      timestamp=self.pim.imported,
                      template=self.msg)

    def import_easydmp(self, plan_export_jsonblob):
        try:
            serialized_dict = deserialize_plan_export(plan_export_jsonblob)
        except PlanImportError as e:
            error_msg = f'{e}, cannot import'
            self.errors.append(error_msg)
            raise

        try:
            with warnings.catch_warnings(record=True) as w:
                pim = import_serialized_plan_export(
                    serialized_dict, self.request.user, self.via
                )
                if w:
                    self.warnings.append(self.request, w[-1].message)
                return pim
        except PlanImportError as e:
            self.errors.append(str(e))
            raise

    def import_rdadcs(self, plan_export_jsonblob):
        try:
            data = load_json_from_stream(
                plan_export_jsonblob, 'Plan', PlanImportError
            )
        except PlanImportError as e:
            error_msg = f'{e}, cannot import'
            self.errors.append(error_msg)
            raise

        try:
            importer = ImportRDA11(data, self.request.user, self.via)
            importer.import_rdadcs()
            return importer.metadata
        except PlanImportError as e:
            self.errors.append(str(e))
            raise
