from collections import defaultdict

from django.db import IntegrityError, transaction
from django.http.request import QueryDict, MultiValueDict

from easydmp.dmpt.models import Template
from easydmp.eestore.models import EEStoreCache
from easydmp.plan.models import AnswerHelper, Answer, Plan, AnswerSet
from easydmp.plan.import_plan import PlanImportError
from easydmp.rdadcs.models import RDADCSKey
from easydmp.rdadcs.models import RDADCSQuestionLink
from easydmp.rdadcs.models import RDADCSSectionLink
from easydmp.rdadcs.models import RDADCSImportMetadata


Unknown = 'Unknown'
RDADCS_UUID = 'f76876bb-697f-4f67-9788-d7887c0f99d4'


def dict_to_querydict(dict_):
    mvdict = MultiValueDict({
        key: data if isinstance(data, list) else [data]
        for key, data in dict_.items()
    })
    qdict = QueryDict('', mutable=True)
    qdict.update(mvdict)
    return qdict


class RDADCSImportError(PlanImportError):
    pass


class ImportRDA10:
    """Initialize then run instance.import_rdadcs()"""

    OBJECT_PATHS = set((
        '.dmp.contact',
        '.dmp.contributor[]?',
        '.dmp.cost[]?',
        '.dmp.dataset[]',
        '.dmp.dataset[].distribution[]?',
        '.dmp.dataset[].distribution[]?.host?',
        '.dmp.dataset[].distribution[]?.license[]?',
        '.dmp.dataset[].metadata[]?',
        '.dmp.dataset[].security_and_privacy[]?',
        '.dmp.dataset[].technical_resource[]?',
        '.dmp.project[]?',
        '.dmp.project[]?.funding[]?',
    ))
    ERROR = "The provided json is not valid RDA DCS"

    def __init__(self, jsonblob, importer, via=None):
        self.jsonblob = jsonblob
        self.owner = importer
        self.via = via
        self.template = Template.objects.get(uuid=RDADCS_UUID)
        self.validate_json(jsonblob)
        self.title = self.jsonblob['dmp']['title']
        # cache some expensive lookups
        self.slugpathmap = self.map_slugs_to_paths()
        self.linkmap = self.map_question_paths()
        self.section_map = self.map_section_paths()
        self.plan = None
        self.metadata = None
        self.answersets = None

    @transaction.atomic()
    def import_rdadcs(self):
        # create prerequisites
        self.plan = self.create_empty_plan()
        self.answersets = self.plan.answersets.select_related('section').order_by('parent', 'section', 'id')
        self.metadata = self.create_import_metadata(self.via)

        # parse and convert to plan
        parent_path = '.dmp'
        jsonblob = self.jsonblob['dmp']

        # Obligatory
        self.do_subpaths_of_flat_path(jsonblob, parent_path)
        try:
            self.do_subpaths_of_flat_path(jsonblob['contact'], '.dmp.contact')
        except KeyError:
            raise RDADCSImportError(f"{self.ERROR}: the contact object is missing")
        try:
            self.do_dataset(jsonblob['dataset'])
        except KeyError:
            raise RDADCSImportError(f"{self.ERROR}: the dataset object is missing")

        # Optional
        if 'contributor' in jsonblob:
            self.do_contributor(jsonblob['contributor'])
        if 'cost' in jsonblob:
            self.do_subpaths_of_repeated_paths_with_one_subpath(
                jsonblob['cost'],
                '.dmp.cost[]?',
            )
        if 'project' in jsonblob:
            self.do_subpaths_of_repeated_paths_with_one_subpath(
                jsonblob['project'],
                '.dmp.project[]?',
                '.dmp.project[]?.funding[]?',
            )

    def validate_json(self, jsonblob):
        if not isinstance(jsonblob, dict):
            raise RDADCSImportError(f"{self.ERROR}: not an object")
        keys = self.jsonblob.keys()
        if not 'dmp' in keys:
            raise RDADCSImportError(f"{self.ERROR}: the \"dmp\" key is missing from the object")
        if len(self.jsonblob.keys()) > 1:
            raise RDADCSImportError(f"{self.ERROR}: there are other keys in the object than \"dmp\"")
        # jsonblob['dmp'] exists
        missing_keys = []
        for key in ('title', 'created', 'modified', 'dmp_id'):
            if not self.jsonblob['dmp'].get(key, None):
                missing_keys.append(key)
        if missing_keys:
            keys = ', '.join(missing_keys)
            raise RDADCSImportError(f"{self.ERROR}: the following key(s) are missing from the dmp object: {keys}")

    def create_import_metadata(self, via=None):
        created = self.jsonblob['dmp']['created']
        modified = self.jsonblob['dmp']['modified']
        try:
            id_ = self.jsonblob['dmp']['dmp_id']['identifier']
            id_type = self.jsonblob['dmp']['dmp_id']['type']
        except KeyError as e:
            raise RDADCSImportError(f"{self.ERROR}: the dmp identifier is incomplete")
        rdadcs_metadata = RDADCSImportMetadata(
            plan=self.plan,
            original_id=id_,
            original_id_type=id_type,
            originally_created=created,
            originally_modified=modified,
            original_json=self.jsonblob,
        )
        if via:
            rdadcs_metadata.via = via
        rdadcs_metadata.save()
        return rdadcs_metadata

    def map_slugs_to_paths(self):
        mapping = {}
        for key in RDADCSKey.objects.all():
            mapping[key.slug] = key.path
        return mapping

    def map_question_paths(self):
        qids = self.template.questions.values_list('pk', flat=True)
        links = (RDADCSQuestionLink.objects
                 .select_related('question', 'question__section', 'key')
                 .filter(question_id__in=qids)
        )
        mapping = {}
        for link in links:
            question = link.question
            mapping[link.key.path] = {
                'question': question,
                'key': link.key,
            }
        return mapping

    def map_section_paths(self):
        sids = self.template.sections.values_list('pk', flat=True)
        links = (RDADCSSectionLink.objects
                 .select_related('section', 'key')
                 .filter(section_id__in=sids)
        )
        mapping = {}
        for link in links:
            mapping[link.key.path] = link.section
        return mapping

    def create_empty_plan(self):
        plan = Plan(
            title=self.title,
            template=self.template,
            added_by=self.owner,
            modified_by=self.owner,
        )
        plan.save()
        return plan

    def get_paths(self, jsonblob, parent_path):
        try:
            keys = jsonblob.keys()
        except AttributeError:
            return
        paths = set()
        for key in keys:
            slug = RDADCSKey.slugify_path(f'{parent_path}.{key}')
            try:
                path = self.slugpathmap[slug]
            except KeyError:
                continue
            if path in self.OBJECT_PATHS:
                continue
            paths.add(path)
        return paths

    @classmethod
    def _convert_trilean_from_rdadcs(cls, trilean):
        return trilean.capitalize()

    @classmethod
    def _convert_externalchoice_from_rdadcs(cls, eestore_pid, question):
        eestoremount = question.eestore
        cache = EEStoreCache.objects.get(
            source__in=eestoremount.sources.all(),
            pid=eestore_pid,
        )
        return cache.eestore_pid

    def import_key(self, value, question, answerset):
        answer = AnswerHelper(question, answerset)
        notesform = answer.get_empty_bound_notesform()
        prefix = answer.prefix
        if str(question.input_type) == 'typedidentifier':
            wrapped_value = {
                f'{prefix}-choice_0': [value['identifier']],
                f'{prefix}-choice_1': [value['type']],
            }
        elif str(question.input_type) == 'multistring':
            rownum = len(value)
            wrapped_value = {
                f'{prefix}-TOTAL_FORMS': rownum,
                f'{prefix}-INITIAL_FORMS': rownum,
            }
            for i, row in enumerate(value):
                wrapped_value[f'{prefix}-{i}-choice'] = row
        else:
            wrapped_value = {f'{prefix}-choice': value}
        wrapped_value = dict_to_querydict(wrapped_value)
        form = answer.get_form(data=wrapped_value)
        form.is_valid()
        try:
            if not form.is_valid():
                errors = '. '.join(form._errors['choice'])
                raise ValueError(errors)
            answer.update_answer_via_forms(form, notesform, self.owner)
        except IntegrityError as e:
            if str(question.input_type) == 'typedidentifier':
                raise ValueError(f'Unique id reused: {e}')
            raise
        return answer

    # Generic parsers of sub objects

    def do_subpaths_of_flat_path(self, jsonblob, parent_path, answerset=None, parent=None):
        """Parse all keys in an object that are not themselves objects

        Identifying objcets are a special case.

        For subobjects that are not repeated (key or key?)
        """
        paths = self.get_paths(jsonblob, parent_path)
        bad_keys = set()
        if not answerset:
            section = self.section_map[parent_path]
            answersets = self.answersets.filter(section=section)
            if parent:
                answersets = answersets.filter(parent=parent)
            answerset = answersets.get()
        if not paths:
            return
        answers = []
        for path in sorted(paths):
            try:
                link = self.linkmap[path]
            except KeyError:
                bad_keys.add(path)
                continue

            keyobj = link['key']
            question = link['question']
            value = jsonblob[keyobj.key]
            if keyobj.input_type_id == 'trilean':
                value = self._convert_trilean_from_rdadcs(value)
            elif keyobj.input_type_id == 'externalchoice':
                value = self._convert_externalchoice_from_rdadcs(value, question)

            section = question.section
            try:
                answer = self.import_key(value, question, answerset)
            except ValueError as e:
                msg = f'Cannot import path "{path}": {e}'
                raise RDADCSImportError(msg)
        return bad_keys

    def do_subpaths_of_repeated_path(self, jsonblob, parent_path, parent=None):
        "For subobjects that are repeated (key[] or key[]?)"
        section = self.section_map[parent_path]

        # Item 1
        answerset = self.answersets.get(section=section, parent=parent)
        entry = jsonblob[0]
        self.do_subpaths_of_flat_path(entry, parent_path, answerset)

        # Item 2—n
        for entry in jsonblob[1:]:
            answerset = answerset.add_sibling()
            self.do_subpaths_of_flat_path(entry, parent_path, answerset)

    def do_subpaths_of_repeated_paths_with_one_subpath(self, jsonblob, parent_path, child_path=None):
        section = self.section_map[parent_path]

        # Item 1
        answerset = self.answersets.get(section=section)
        entry = jsonblob[0]
        self.do_subpaths_of_flat_path(entry, parent_path, answerset)
        child_key = None
        if child_path:
            child_key, *_ = RDADCSKey.get_key(child_path)
            self.do_subpaths_of_repeated_path(entry[child_key], child_path, parent=answerset)

        # Item 2—n
        for entry in jsonblob[1:]:  # list
            answerset = answerset.add_sibling()
            self.do_subpaths_of_flat_path(entry, parent_path, answerset)
            if child_path:
                self.do_subpaths_of_repeated_path(entry[child_key], child_path, parent=answerset)

    # Specific parsers for subobjects that have subobjects

    def do_contributor(self, jsonblob):
        parent_path = '.dmp.contributor[]?'
        section = self.section_map[parent_path]

        # Item 1
        answerset = self.answersets.get(section=section)
        entry = jsonblob[0]
        self.do_subpaths_of_flat_path(entry, parent_path, answerset)

        # Item 2—n
        for entry in jsonblob[1:]:  # list
            answerset = answerset.add_sibling()
            self.do_subpaths_of_flat_path(entry, parent_path, answerset)

    def do_dataset(self, jsonblob):
        parent_path = '.dmp.dataset[]'
        section = self.section_map[parent_path]

        # Item 1
        entry = jsonblob[0]
        answerset = self.answersets.get(section=section)
        self.do_single_dataset(entry, parent_path, answerset)

        # Item 2—n
        for entry in jsonblob[1:]:  # list
            answerset = answerset.add_sibling()
            self.do_single_dataset(entry, parent_path, answerset)

    def do_single_dataset(self, jsonblob, parent_path, answerset):
        self.do_subpaths_of_flat_path(jsonblob, parent_path, answerset)
        subobjects = {
            '.dmp.dataset[].metadata[]?': 'metadata',
            '.dmp.dataset[].security_and_privacy[]?': 'security_and_privacy',
            '.dmp.dataset[].technical_resource[]?': 'technical_resource',
        }
        for path, key in subobjects.items():
            if key in jsonblob:
                self.do_subpaths_of_repeated_path(jsonblob[key], path, parent=answerset)
        # .dmp.dataset[].distribution[]?
        if 'distribution' in jsonblob:
            self.do_distribution(jsonblob['distribution'], answerset)

    def do_distribution(self, jsonblob, parent):
        parent_path = '.dmp.dataset[].distribution[]?'
        section = self.section_map[parent_path]

        answerset = self.answersets.get(section=section, parent=parent)
        entry = jsonblob[0]

        # Item 1
        self.do_single_distribution(entry, parent_path, answerset)

        # Item 2—n
        for entry in jsonblob[1:]:  # list
            answerset = answerset.add_sibling()
            self.do_single_distribution(entry, parent_path, answerset)

    def do_single_distribution(self, jsonblob, parent_path, answerset):
        self.do_subpaths_of_flat_path(jsonblob, parent_path, answerset)
        if 'host' in jsonblob:
            entry = jsonblob['host']
            path = '.dmp.dataset[].distribution[]?.host?'
            self.do_subpaths_of_flat_path(entry, path, parent=answerset)
        if 'license' in jsonblob:
            entry = jsonblob['license']
            path = '.dmp.dataset[].distribution[]?.license[]?'
            self.do_subpaths_of_repeated_path(entry, path, parent=answerset)
