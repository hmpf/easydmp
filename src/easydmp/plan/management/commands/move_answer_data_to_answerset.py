from django.core.management import BaseCommand

from easydmp.plan.models import Plan


class Command(BaseCommand):
    help = "Distribute answer data from Plan to appropriate AnswerSet"

    def add_arguments(self, parser):
        parser.add_argument('-p', '--plan', nargs='*', type=int, default=[],
                            help='Plans to process (id). Default is all plans.')

    def handle(self, *args, **options):
        plan_ids = options['plan']
        if plan_ids:
            plans = Plan.objects.filter(pk__in=plan_ids)
        else:
            plans = Plan.objects.all()
        