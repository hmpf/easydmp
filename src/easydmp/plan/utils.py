from django.contrib.auth import get_user_model


def purge_answer(answerset, question_pk, purged_by=None):
    "Delete and return the answer for the specified answerset and question id"

    data = answerset.data
    data.pop(question_pk, None)
    prevdata = answerset.previous_data
    prevdata.pop(question_pk, None)
    answerset.data = data
    answerset.previous_data = prevdata
    answerset.save()
    if purged_by:
        answerset.plan.modified_by = purged_by
    answerset.plan.save(user=purged_by)
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
    from easydmp.plan.models import Plan, AnswerSet
    from easydmp.dmpt.models import Template, Section

    plans_with_answers = tuple(AnswerSet.objects
        .exclude(skipped=True)
        .exclude(data={})
        .values_list('plan_id', flat=True).distinct()
    )
    plan_qs = Plan.objects.filter(id__in=plans_with_answers)
    template_qs = Template.objects.all()
    if template_ids:
        template_qs = Template.objects.filter(id__in=template_ids)
    section_qs = Section.objects.all()
    if section_ids:
        section_qs = Section.objects.filter(id__in=section_ids)
        template_qs = template_qs.filter(sections__in=section_qs)
    plan_qs = plan_qs.filter(template__in=template_qs)
    if plan_ids:
        plan_qs = plan_qs.filter(id__in=plan_ids)

    return plan_qs, template_qs, section_qs


# Deprecated. Remove after squashing plan migrations
def create_plan_editor_group(plan):
    # Located here in order to be accessible from migrations
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name='plan-editors-{}'.format(plan.pk))
    plan.editor_group = group
    plan.save()
