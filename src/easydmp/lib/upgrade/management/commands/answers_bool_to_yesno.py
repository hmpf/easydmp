# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Question
from easydmp.lib.convert.answers import bool_to_yesno
from easydmp.lib.convert.answers import convert_plan_answers
from easydmp.plan.models import Plan


class Command(BaseCommand):
    help = "Convert a plan's bool answers to yes/no"

    def add_arguments(self, parser):
        parser.add_argument('plan_id', nargs='+', type=int)

    def handle(self, *args, **options):
        verbose = options['verbosity'] > 1
        plan_ids = options['plan_id']
        plans = Plan.objects.filter(id__in=plan_ids)
        question_ids = (Question.objects
                        .filter(input_type='bool')
                        .values_list('id', flat=True))
        convert_plan_answers(bool_to_yesno, question_ids, plans, verbose)
