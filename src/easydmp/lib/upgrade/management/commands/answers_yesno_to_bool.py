# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Question
from easydmp.lib.convert.answers import convert_plan_answers
from easydmp.lib.convert.answers import yesno_to_bool
from easydmp.plan.models import Plan


class Command(BaseCommand):
    help = "Convert a plan's yes/no answers to bool"

    def add_arguments(self, parser):
        parser.add_argument('plan_id', nargs='+', type=int)

    def handle(self, *args, **options):
        verbose = options['verbosity'] > 1
        plan_ids = options['plan_id']
        plans = Plan.objects.filter(id__in=plan_ids)
        question_ids = (Question.objects
                        .filter(input_type='bool')
                        .values_list('id', flat=True))
        convert_plan_answers(yesno_to_bool, question_ids, plans, verbose)
