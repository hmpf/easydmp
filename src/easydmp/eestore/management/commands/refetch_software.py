from django.core.management.base import BaseCommand, CommandError

from easydmp.eestore.plugins import software_biotools


class Command(BaseCommand):
    help = "(Re)fetch data for specified software source"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='command', required=False)
        biotools = subparsers.add_parser('biotools', help="Fetch from biotools")
        biotools.add_argument('-a', '--after', type=software_biotools.parse_datetime)
        biotools.add_argument('-f', '--force', action='store_true')
        in_or_out = biotools.add_mutually_exclusive_group()
        in_or_out.add_argument('-i', '--input', type=str, help='Fetch from file containing ndjson stored dump')
        in_or_out.add_argument('-o', '--output', type=str, help='Store ndjson dump in file')

    def get_outfilehandler(self, filename=None):
        if not filename:
            return None
        File = None
        if filename:
            if filename == '-':
                File = self.sys.stdout
            else:
                File = open(filename, 'a')
        return File

    def get_infilehandler(self, filename=None):
        if not filename:
            return None
        File = None
        if filename:
            if filename == '-':
                File = self.sys.stdin
            else:
                File = open(filename, 'r')
        return File

    def handle(self, *args, **options):
        command = options.get('command', None)
        verbose = bool(options['verbosity'])
        if not command:
            return
        if command == 'biotools':
            force = options.get('force', False)
            OutFile = self.get_outfilehandler(options.get('output', None))
            InFile = self.get_infilehandler(options.get('input', None))
            last_fetched = options.get('after', None)
            software_biotools.refetch_entries(force, last_fetched, verbose, OutFile, InFile)
        else:
            raise CommandError(f"Unsupported source for software: {command}")
