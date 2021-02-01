import argparse
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.export_template import serialize_template_export
from easydmp.dmpt.models import Template

class Command(BaseCommand):
    help = "Export a template and all its dependencies to a json dump"

    def add_arguments(self, parser):
        parser.add_argument('template', type=int,
                            help='Export the template with pk PK')
        parser.add_argument('filename', nargs='?', default=self.stdout,
                            type=argparse.FileType('w'),
                            help='Write to FILE, default: stdout')
        parser.add_argument('--indent', type=int,
                            help='Indent by N characters')
        parser.add_argument('-c', '--comment', type=str,
                            help='Add a comment')

    def handle(self, *args, **options):
        filename = options['filename'] or None
        template_id = options['template']
        comment = options.get('comment') or ''
        indent = options.get('indent') or None

        try:
            serialized_object = serialize_template_export(template_id)
        except Template.DoesNotExist:
            self.stderr.write(f'Template with id {template_id} does not exist, aborting')
            sys.exit(1)
        data = serialized_object.data
        data['comment'] = comment
        blob = json.dumps(data, indent=indent)
        filename.write(blob)
