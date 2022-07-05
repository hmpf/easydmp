import argparse
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from easydmp.plan.models import Plan
from easydmp.rdadcs.lib.export_plan import GenerateRDA11

class Command(BaseCommand):
    help = "Export a plan and all its dependencies to a json dump"

    def add_arguments(self, parser):
        parser.add_argument('plan', type=int,
                            help='Export the plan with pk PK')
        parser.add_argument('filename', nargs='?', default=self.stdout,
                            type=argparse.FileType('w'),
                            help='Write to FILE, default: stdout')
        parser.add_argument('--indent', type=int,
                            help='Indent by N characters')

    def handle(self, *args, **options):
        filename = options['filename'] or None
        plan_id = options['plan']
        indent = options.get('indent') or None

        try:
            plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            self.stderr.write(f'Plan with id {plan_id} does not exist, aborting')
            sys.exit(1)
        data = GenerateRDA11(plan).json()
        blob = json.dumps(data, indent=indent)
        filename.write(blob)
