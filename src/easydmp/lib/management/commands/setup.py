from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from easydmp.auth.setup import setup_auth_tables, setup_dev_users


EESTORE_FIXTURE_PATH= 'fixtures/eestore.dumpdata.json.zip'
EXAMPLE_TEMPLATE_DIRECTORY = 'plan-templates'
EXAMPLE_TEMPLATES = (
)


class Command(BaseCommand):
    help = "Setup a new site by filling some tables with standardized data"

    def add_arguments(self, parser):
        parser.add_argument('--database', type=str,
                            help='Nominates a specific database to load fixtures into. Defaults to the "default" database',
                            default='default')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--development', action='store_true',
                           help='Add development relevant data: example users and templates and cached EEStore data')
        group.add_argument('--eestore', action='store_true',
                            help='Load a cache of EEStore data')


    def handle(self, *args, **options):
        database = options['database']
        setup_auth_tables()
        self.stdout.write('Created group "Template Designer"')

        if options['development']:
            options['eestore'] = True
            setup_dev_users()
            self.stdout.write('Created development users "superuser", "ordinaryuser" and "templatedesigner".')
            self.stdout.write('Change their passwords with "manage.py changepassword <username>".')

            for template in EXAMPLE_TEMPLATES:
                template_file = f'{EXAMPLE_TEMPLATE_DIRECTORY}/{template}'
                call_command('import_complete_template', template_file,
                             origin='examples', database=database)
                self.stdout.write(f'Imported template from file {template_file}')

        if options['eestore']:
            call_command('loaddata', 'fixtures/eestore.dumpdata.json.zip',
                         ignorenonexistent=True, database=database)
            self.stdout.write('Loaded cached data from EEStore')
