from collections import defaultdict

from easydmp.eestore.models import EEStoreCache
from easydmp.plan.models import AnswerHelper
from easydmp.rdadcs.models import RDADCSKey, RDADCSQuestionLink, RDADCSSectionLink


Unknown = 'Unknown'


class GenerateRDA11:
    """
    A minimal WIP RDA DMP CS serializer
    """

    def __init__(self, plan):
        self.plan = plan
        self.answersets = self.plan.answersets.exclude(skipped=True).filter(
            valid=True,
        )
        self.rda_question_links = self.get_rda_question_links()
        self.rda_section_links = self.get_rda_section_links()

    def get_rda_question_links(self):
        mapping = defaultdict(dict)
        for answerset in self.answersets:
            qids = answerset.data.keys()
            links = RDADCSQuestionLink.objects.filter(
                question_id__in=map(int, qids)
            )
            for link in links:
                mapping[link.key.path][answerset.id] = AnswerHelper(link.question, answerset)
        return mapping

    def get_rda_section_links(self):
        mapping = dict()
        links = RDADCSSectionLink.objects.filter(
            section__in=self.plan.template.sections.all()
        ).select_related('key')
        for link in links:
            mapping[link.key.path] = link.section_id
        return mapping

    def _get_answerhelper_for_path(self, path, answerset_id=None):
        if path in self.rda_question_links:
            if not answerset_id:
                answerset_id = next(iter(self.rda_question_links[path]))
            return self.rda_question_links[path].get(answerset_id, None)
        return None

    def _convert_externalchoice_to_rdadcs(cls, eestore_pid, question):
        if not eestore_pid:
            return None
        eestoremount = question.eestore
        cache = EEStoreCache.objects.get(
            source__in=eestoremount.sources.all(),
            eestore_pid=eestore_pid,
        )
        return cache.pid

    def _get_key_value_for_path(self, path, answerset_id=None, fallback=None):
        key, *_ = RDADCSKey.get_key(path)
        ah = self._get_answerhelper_for_path(path, answerset_id)
        if not ah:
            return key, fallback
        value = ah.current_choice['choice']
        if str(ah.question.input_type) == 'externalchoice':
            value = self._convert_externalchoice_to_rdadcs(value, ah.question)
        elif str(ah.question.input_type) == 'trilean':
            value = value.lower()
        return key, value or fallback

    def _get_key(self, rules, answerset_id):
        data = {}
        complete = True
        for path, fallback in rules:
            key, optional, _ = RDADCSKey.parse_key(path)
            key, value = self._get_key_value_for_path(path, answerset_id, fallback)
            if not optional and not value:
                complete = False
                break
            if value:
                data[key] = value
        return data if complete else None

    def _get_flat_list(self, path, rules, parent_answerset_id=None):
        key, *_ = RDADCSKey.get_key(path)
        _, _, repeatable = RDADCSKey.parse_key(path)
        section_id = self.rda_section_links[path]
        data = []
        answersets = self.answersets.filter(section_id=section_id)
        if parent_answerset_id:
            answersets = answersets.filter(parent_id=parent_answerset_id)
        for answerset in answersets:
            entry = self._get_key(rules, answerset.id)
            if entry:
                data.append(entry)
        if data and not repeatable:
            data = data[0]
        return key, data

    def json(self):
        key, value = self.get_dmp()
        return {key: value}

    def get_dmp(self):
        dmp = {}

        RULES = [
            ('.dmp.dmp_id', self._get_fallback_id()),
            ('.dmp.title', self.plan.title),
            ('.dmp.description?', None),
            ('.dmp.created', self._format_datetime(self.plan.added)),
            ('.dmp.modified', self._format_datetime(self.plan.modified)),
            ('.dmp.language', 'eng'),
            ('.dmp.ethical_issues_exist', Unknown),
            ('.dmp.ethical_issues_description?', None),
            ('.dmp.ethical_issues_report?', None),
        ]
        for path, fallback in RULES:
            key, value = self._get_key_value_for_path(path, None, fallback)
            if value:
                dmp[key] = value

        COMPLEX_KEY_RULES = [
            self.get_contact_object(),
            self.get_contributor_list(),
            self.get_dataset_list(),
            self.get_project_list(),
            self.get_cost_list(),
        ]
        for key, value in COMPLEX_KEY_RULES:
            if value:
                dmp[key] = value
        return 'dmp', dmp

    def get_contact_object(self):
        PATH = '.dmp.contact'
        RULES = [
            ('.dmp.contact.contact_id', None),
            ('.dmp.contact.mbox', None),
            ('.dmp.contact.name', None),
        ]
        section_id = self.rda_section_links[PATH]
        answerset = self.answersets.get(section_id=section_id)
        data = self._get_key(RULES, answerset.id)
        if not data:
            data = self._get_metadata_person(self.plan.added_by, 'contact_id')
        return 'contact', data

    def get_contributor_list(self):
        PATH = '.dmp.contributor[]?'
        RULES = [
            ('.dmp.contributor[]?.contributor_id', None),
            ('.dmp.contributor[]?.mbox', None),
            ('.dmp.contributor[]?.name', None),
            ('.dmp.contributor[]?.role[]', ['other']),
        ]
        key, data = self._get_flat_list(PATH, RULES)
        if not data:
            data = self._get_metadata_contributor()
        return key, data

    def get_dataset_list(self):
        PATH = '.dmp.dataset[]'
        RULES = [
            ('.dmp.dataset[].dataset_id', self._get_fallback_id()),
            ('.dmp.dataset[].title', self.plan.title),
            ('.dmp.dataset[].description?', None),
            ('.dmp.dataset[].data_quality_assurance[]?', None),
            ('.dmp.dataset[].issued?', None),
            ('.dmp.dataset[].keyword[]?', None),
            ('.dmp.dataset[].language?', None),
            ('.dmp.dataset[].personal_data', Unknown),
            ('.dmp.dataset[].preservation_statement?', None),
            ('.dmp.dataset[].sensitive_data', Unknown),
            ('.dmp.dataset[].type?', None),
        ]
        SUBRULES = {
            '.dmp.dataset[].metadata[]?': [
                ('.dmp.dataset[].metadata[]?.description?', None),
                ('.dmp.dataset[].metadata[]?.language', None),
                ('.dmp.dataset[].metadata[]?.metadata_standard_id', None),
            ],
            '.dmp.dataset[].security_and_privacy[]?': [
                ('.dmp.dataset[].security_and_privacy[]?.title', None),
                ('.dmp.dataset[].security_and_privacy[]?.description?', None),
            ],
            '.dmp.dataset[].technical_resource[]?': [
                ('.dmp.dataset[].technical_resource[]?.name', None),
                ('.dmp.dataset[].technical_resource[]?.description?', None),
            ],
        }
        section_id = self.rda_section_links[PATH]
        data = []
        for answerset in self.answersets.filter(section_id=section_id):
            entry = self._get_key(RULES, answerset.id)
            # distribution
            key, dist_entries = self.get_distribution_list(answerset.id)
            if dist_entries:
                entry[key] = dist_entries
            # metadata, security_and_privacy, technical_resource
            for subpath, subrules in SUBRULES.items():
                subkey, subentries = self._get_flat_list(subpath, subrules, answerset.id)
                if subentries:
                    entry[subkey] = subentries
            data.append(entry)
        return 'dataset', data

    def get_distribution_list(self, parent_answerset_id):
        PATH = '.dmp.dataset[].distribution[]?'
        RULES = [
            ('.dmp.dataset[].distribution[]?.title', None),
            ('.dmp.dataset[].distribution[]?.description?', None),
            ('.dmp.dataset[].distribution[]?.access_url?', None),
            ('.dmp.dataset[].distribution[]?.available_until?', None),
            ('.dmp.dataset[].distribution[]?.byte_size?', None),
            ('.dmp.dataset[].distribution[]?.data_access', None),
            ('.dmp.dataset[].distribution[]?.download_url?', None),
            ('.dmp.dataset[].distribution[]?.format[]?', None),
        ]
        SUBRULES = {
            '.dmp.dataset[].distribution[]?.host?': [
                ('.dmp.dataset[].distribution[]?.host?.title', None),
                ('.dmp.dataset[].distribution[]?.host?.availability?', None),
                ('.dmp.dataset[].distribution[]?.host?.backup_frequency?', None),
                ('.dmp.dataset[].distribution[]?.host?.backup_type?', None),
                ('.dmp.dataset[].distribution[]?.host?.certified_with?', None),
                ('.dmp.dataset[].distribution[]?.host?.description?', None),
                ('.dmp.dataset[].distribution[]?.host?.geo_location?', None),
                ('.dmp.dataset[].distribution[]?.host?.pid_system[]?', None),
                ('.dmp.dataset[].distribution[]?.host?.storage_type?', None),
                ('.dmp.dataset[].distribution[]?.host?.support_versioning?', None),
                ('.dmp.dataset[].distribution[]?.host?.url', None),
            ],
            '.dmp.dataset[].distribution[]?.license[]?': [
                ('.dmp.dataset[].distribution[]?.license[]?.license_ref', None),
                ('.dmp.dataset[].distribution[]?.license[]?.start_date', None),
            ],
        }
        section_id = self.rda_section_links[PATH]
        data = []
        for answerset in self.answersets.filter(
                section_id=section_id,
                parent_id=parent_answerset_id,
        ):
            entry = self._get_key(RULES, answerset.id)
            for subpath, subrules in SUBRULES.items():
                subkey, subentries = self._get_flat_list(subpath, subrules, answerset.id)
                if subentries:
                    entry[subkey] = subentries
            data.append(entry)
        return 'distribution', data

    def get_project_list(self):
        PATH = '.dmp.project[]?'
        RULES = [
            ('.dmp.project[]?.title', None),
            ('.dmp.project[]?.description?', None),
            ('.dmp.project[]?.start?', None),
            ('.dmp.project[]?.end?', None),
        ]
        FUNDING_RULES = [
            ('.dmp.project[]?.funding[]?.funder_id', None),
            ('.dmp.project[]?.funding[]?.funding_status?', None),
            ('.dmp.project[]?.funding[]?.grant_id?', None),
        ]
        section_id = self.rda_section_links[PATH]
        data = []
        for answerset in self.answersets.filter(section_id=section_id):
            entry = self._get_key(RULES, answerset.id)
            key, funding_entries = self._get_flat_list(
                '.dmp.project[]?.funding[]?',
                FUNDING_RULES,
                answerset.id,
            )
            if funding_entries:
                entry[key] = funding_entries
            data.append(entry)
        return 'project', data

    def get_cost_list(self):
        PATH = '.dmp.cost[]?'
        RULES = [
            ('.dmp.cost[]?.currency_code', None),
            ('.dmp.cost[]?.description', None),
            ('.dmp.cost[]?.title', None),
            ('.dmp.cost[]?.value', None),
        ]
        key, data = self._get_flat_list(PATH, RULES)
        if not data:
            data = self._get_cost_from_dedicated_field()
        return key, data

    def _get_cost_from_dedicated_field(self):
        cost_question_pairs = (self.plan.template.questions
                               .filter(input_type='multirdacostonetext')
                               .values_list('id', 'section'))
        cost_list = []
        for qid, section in cost_question_pairs:
            qid = str(qid)
            answersets = self.plan.answersets.filter(section=section)
            for answerset in answersets:
                costs = answerset.get_choice(qid) or []
                # Hide unset fields
                for cost in costs:
                    filtered_cost = {k: v for k, v in cost.items() if v}
                    cost_list.append(filtered_cost)
        return cost_list

    # fallback methods: reuse/reformat metadata common to all plans
    # to fake some obligatory fields

    def _format_datetime(self, dt):
        return dt.isoformat()

    def _get_metadata_person(self, person, id_name='id'):
        if not person:
            return {}
        email_address = person.email or person.username
        full_name = person.get_full_name() or email_address
        identifier = str(person.id)
        return {
            'mbox': email_address,
            'name': full_name,
            id_name: {
                'identifier': identifier,
                'type': 'other',
            }
        }

    def _get_metadata_contributor(self):
        has_made_changes = set((self.plan.added_by, self.plan.modified_by,
                                self.plan.locked_by, self.plan.published_by))
        has_made_changes.discard(None)
        editors = set(access.user for access in self.plan.accesses.all())
        raw_contributors = has_made_changes | editors
        contributors = []
        for contributor in raw_contributors:
            data = self._get_metadata_person(contributor, 'contributor_id')
            data['role'] = [Unknown]
            contributors.append(data)
        return contributors or None

    def _get_fallback_id(self):
        # dmp_id and dataset_id are obligatory
        return {
            'identifier': str(self.plan.uuid),
            'type': 'other',
        }
