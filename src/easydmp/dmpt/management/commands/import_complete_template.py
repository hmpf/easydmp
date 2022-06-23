import argparse
import json
import sys
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.import_template import (
    deserialize_template_export,
    import_or_get_template,
    TemplateImportError
)


class Command(BaseCommand):
    help = "Import a template and all its dependencies from a json dump"

    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='?', default=sys.stdin,
                            type=argparse.FileType('rb'),
                            help='Read from FILE, default: stdin')
        parser.add_argument('-o', '--origin', type=str,
                            help='Origin, to make this import unique. Default: UUID 4')

    def handle(self, *args, **options):
        origin = options['origin'] or uuid4()
        filename = options['filename'] or None

        raw_blob = filename.read()
        filename.close()
        try:
            serialized_dict = deserialize_template_export(raw_blob)
        except TemplateImportError as e:
            self.stderr.write(f"{e}, cannot import")
            sys.exit(1)
        try:
            tim = import_or_get_template(serialized_dict, origin=origin, via='CLI')
        except TemplateImportError as e:
            self.stderr.write(str(e))
            sys.exit(1)
        else:
            self.stdout.write(f'Successfully imported "{tim.template}", origin set to "{tim.origin}"')
