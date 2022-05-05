from django.core.management.base import BaseCommand, CommandError

from easydmp.rdadcs.lib.csv import load_rdadcs_from_csv

load_help = """Load RDA DCS paths with matching EasyDMP types from csv file

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
        with open(filename, 'r') as FILE:
            load_rdadcs_from_csv(FILE, self.stderr, csv_options)
