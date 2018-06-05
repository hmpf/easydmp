from django.contrib.auth import get_user_model


def purge_answer(plan, question_pk):
    "Delete and return the answer for the specified plan and question id"

    data = plan.data
    data.pop(question_pk, None)
    prevdata = plan.previous_data
    prevdata.pop(question_pk, None)
    plan.data = data
    plan.previous_data = prevdata
    plan.save()
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


def create_plan_editor_group(plan):
    # Located here in order to be accessible from migrations
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name='plan-editors-{}'.format(plan.pk))
    plan.editor_group = group
    plan.save()
