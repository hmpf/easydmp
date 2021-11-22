import argparse
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from easydmp.plan.export_plan import serialize_plan_export
from easydmp.plan.models import Plan

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
        parser.add_argument('-c', '--comment', type=str,
                            help='Add a comment')

    def handle(self, *args, **options):
        filename = options['filename'] or None
        plan_id = options['plan']
        comment = options.get('comment') or ''
        indent = options.get('indent') or None

        try:
            serialized_object = serialize_plan_export(plan_id, comment=comment)
        except Plan.DoesNotExist:
            self.stderr.write(f'Plan with id {plan_id} does not exist, aborting')
            sys.exit(1)
        data = serialized_object.data
        blob = json.dumps(data, indent=indent)
        filename.write(blob)
