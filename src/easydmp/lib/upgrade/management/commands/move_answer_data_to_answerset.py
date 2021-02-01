from typing import List

from django.core.management import BaseCommand

from easydmp.dmpt.models import Question
from easydmp.plan.models import Plan, AnswerSet


#
# This was part of a refactor to change ownership of answer data, and may be deleted later.
#

def handle_plan(plan: Plan, delete: bool):
    for k, d in dict(plan.data).items():
        question = Question.objects.get(pk=int(k))
        answerset = AnswerSet.objects.get(section=question.section)
        answerset.data[k] = d
        answerset.save()
        if delete:
            del plan.data[k]
            plan.save()


class Command(BaseCommand):
    help = "Distribute answer data from Plan to appropriate AnswerSet"

    def add_arguments(self, parser):
        parser.add_argument('-p', '--plans', nargs='*', type=int, default=[],
                            help='Plans to process (id). Default is no plans. Overrides --allplans if set.')
        parser.add_argument('-a', '--allplans', type=bool, default=False,
                            help='Whether to process all plans. Default is false')
        parser.add_argument('-d', '--delete', type=bool, default=False,
                            help='Whether to delete the answer data from Plan after it has been written to AnswerSet. Default is false. The command is idempotent only if this is false.')

    def handle(self, *args, **options):
        plan_ids = options['plans']
        do_all_plans = options['allplans']
        plans = []
        if plan_ids:
            plans = Plan.objects.filter(pk__in=plan_ids)
        elif do_all_plans:
            plans = Plan.objects.all()
        for plan in plans:
            handle_plan(plan, options['delete'])
