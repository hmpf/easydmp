from django.contrib.auth import get_user_model


def purge_answer(plan, question_pk, purged_by=None):
    "Delete and return the answer for the specified plan and question id"

    data = plan.data
    data.pop(question_pk, None)
    prevdata = plan.previous_data
    prevdata.pop(question_pk, None)
    plan.data = data
    plan.previous_data = prevdata
    if purged_by:
        plan.modified_by = purged_by
    plan.save(user=purged_by)
    return {'data': data, 'previous_data': prevdata}


def convert_ee_to_eenotlisted(choice):
    if isinstance(choice, list):
        choices = choice
        not_listed = True
        choice = {'choices': choices, 'not_listed': not_listed}
        return choice
    else:
        return choice


def convert_eenotlisted_to_ee(choice):
    if isinstance(choice, dict):
        return choice['choices']
    else:
        return choice


def get_editors_for_plan(plan):
    # Located here in order to be accessible from migrations
    User = get_user_model()
    pas = plan.accesses.filter(may_edit=True)
    qs = User.objects.filter(plan_accesses__in=pas)
    return qs


def select_plans(plan_ids=(), template_ids=(), section_ids=()):
    from easydmp.plan.models import Plan
    from easydmp.dmpt.models import Template, Section

    plan_qs = Plan.objects.exclude(data={})
    template_qs = Template.objects.all()
    if template_ids:
        template_qs = Template.objects.filter(template_id__in=template_ids)
    section_qs = Section.objects.all()
    if section_ids:
        section_qs = Section.objects.filter(id__in=section_ids)
        template_qs = template_qs.filter(sections__in=section_qs)
    plan_qs = plan_qs.filter(template__in=template_qs)
    if plan_ids:
        plan_qs = plan_qs.filter(id__in=plan_ids)

    return plan_qs, template_qs, section_qs


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
        if not self.plan.data:
            return {}
        cost_question_ids = (self.plan.template.questions
                            .filter(input_type='multirdacostonetext')
                            .values_list('id', flat=True))
        cost_list = []
        for qid in cost_question_ids:
            qid = str(qid)
            # XXX: get the choice in a better way
            costs = self.plan.data.get(str(qid), {}).get('choice', [])
            # Hide unset fields
            for cost in costs:
                filtered_cost = {k: v for k, v in cost.items() if v}
                cost_list.append(filtered_cost)
        return {'cost': cost_list}


# Deprecated. Remove after squashing plan migrations
def create_plan_editor_group(plan):
    # Located here in order to be accessible from migrations
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name='plan-editors-{}'.format(plan.pk))
    plan.editor_group = group
    plan.save()
