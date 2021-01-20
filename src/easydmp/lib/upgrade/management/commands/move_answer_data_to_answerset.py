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
        parser.add_argument('-p', '--plan', nargs='*', type=int, default=[],
                            help='Plans to process (id). Default is all plans.')
        parser.add_argument('-d', '--delete', type=bool, default=False,
                            help='Whether to delete the answer data from Plan after it has been written to AnswerSet. Default is false. The command is idempotent only if this is false.')

    def handle(self, *args, **options):
        plan_ids = options['plan']
        if plan_ids:
            plans = Plan.objects.filter(pk__in=plan_ids)
        else:
            plans = Plan.objects.all()
        for plan in plans:
            handle_plan(plan, options['delete'])
