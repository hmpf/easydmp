from django.core.management.base import BaseCommand, CommandError

from easydmp.rdadcs.lib.csv import dump_rdadcs_to_csv
from easydmp.rdadcs.models import RDADCSKey

load_help = """Dump RDA DCS paths with matching EasyDMP types to csv file

See https://docs.python.org/3/library/csv.html#csv-fmt-params for
an explanation of the csv formatting options "delimiter" and "strict".
"""

class Command(BaseCommand):
    help = load_help

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument('--delimiter', default='\t')
        parser.add_argument('--strict', action='store_true', default=False)

    def handle(self, *args, **options):
        filename = options['filename']
        csv_options = {
            'delimiter': options['delimiter'],
            'strict': options['strict'],
        }
        paths_types = RDADCSKey.objects.values_list('path', 'input_type__pk')
        with open(filename, 'w') as FILE:
            dump_rdadcs_to_csv(paths_types, FILE, self.stderr, csv_options)
