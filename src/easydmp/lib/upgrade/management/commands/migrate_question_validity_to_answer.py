from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from easydmp.plan.models import Answer, Plan, AnswerSet


def update_one_plan(plan_id):
    with transaction.atomic():
        for answer in Answer.objects.filter(plan__id=plan_id, answerset_id__isnull=True).prefetch_related('question', 'question__section'):
            answer.answerset = AnswerSet.objects.get(
                plan=answer.plan,
                section=answer.question.section
            )
            answer.save()


class Command(BaseCommand):
    help = "Add correct AnswerSet to Answer"

    def add_arguments(self, parser):
        parser.add_argument('batch-size', type=int, default=10,
                            help='Do BATCH-SIZE plans, then stop. Default 10')
    def handle(self, *args, **options):
        num = options['batch-size'] or 10

        all_plans_num = Plan.objects.count()
        plans_with_answers_num =Plan.objects.exclude(data={}).count()
        self.stdout.write(f'Plans in total: {all_plans_num}')
        self.stdout.write(f'Plans with at least one answer: {plans_with_answers_num}')
        plan_ids = Answer.objects.filter(answerset_id__isnull=True).only('plan').values_list('plan__id', flat=True).distinct()
        self.stdout.write(f'Plans not properly linked (answerset not set): {plan_ids.count()}')
        plans = Plan.objects.filter(id__in=plan_ids).exclude(data={}).order_by('id')
        self.stdout.write(f'Working on {num} plans (left: max {plans.count()})')
        del plan_ids
        for plan in plans[:num]:
            update_one_plan(plan.id)
            self.stdout.write(f'Updated answers for plan "{plan}", id {plan.id}, template "{plan.template}"')
