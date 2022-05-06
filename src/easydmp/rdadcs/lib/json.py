class GenerateRDA10:
    """
    A minimal WIP RDA DMP CS serializer
    """

    def __init__(self, plan):
        self.plan = plan

    def _get_person_data(self, person, id_name='id'):
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

    def _get_contributor(self, person, roles=None):
        if roles is None:
            roles = ['Unknown']
        data = self._get_person_data(person, 'contributor_id')
        if data:
            data['role'] = roles
        return data

    def _get_plan_metadata(self, id_name='id'):
        plan = {
            'title': self.plan.title,
            id_name: {
                'identifier': str(self.plan.uuid),
                'type': 'other',
            },
        }
        return plan

    def _format_datetime(self, dt):
        return dt.isoformat()

    def get_dmp(self):
        dmp = {
            'dmp': {
                'created': self._format_datetime(self.plan.added),
                'modified': self._format_datetime(self.plan.modified),
                'language': 'eng',
            }
        }
        dmp['dmp'].update(**self._get_plan_metadata('dmp_id'))

        body = dmp['dmp']
        # Obligatory
        body.update(self.get_contact())
        body.update(self.get_dataset())
        body.update(self.get_ethical_issues_exist())

        # Optional
        # `description` not available
        # `ethical_issues_description` from RDATag
        # `ethical_issues_report` from RDATag

        contributors = self.get_contributors()
        if contributors:
            body.update(contributors)
        cost = self.get_cost()
        if cost:
            body.update(cost)

        return dmp

    def get_contact(self):
        data = self._get_person_data(self.plan.added_by, 'contact_id')
        return {'contact': data}

    def get_dataset(self):
        dataset = {
            'personal_data': 'unknown',
            'sensitive_data': 'unknown'
        }
        dataset.update(**self._get_plan_metadata('dataset_id'))
        return {'dataset': [dataset]}

    def get_ethical_issues_exist(self):
        return {'ethical_issues_exist': 'unknown'}

    def get_contributors(self):
        has_made_changes = set((self.plan.added_by, self.plan.modified_by,
                                self.plan.locked_by, self.plan.published_by))
        editors = set(access.user for access in self.plan.accesses.all())
        raw_contributors = has_made_changes | editors
        contributors = []
        for contributor in raw_contributors:
            blob = self._get_contributor(contributor)
            if blob:
                contributors.append(blob)
        if contributors:
            return {'contributor': contributors}
        return {}

    def get_cost(self):
        if self.plan.is_empty:
            return {}
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
        return {'cost': cost_list}
