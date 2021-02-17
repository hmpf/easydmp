from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Reset migration history by emptying the django_migrations table"

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            default=DEFAULT_DB_ALIAS,
            help='Select which database to use. Defaults to the "default" database.',
        )

    def handle(self, *args, **options):
        # Get the database we're operating from
        db = options['database']
        connection = connections[db]

        # Hook for backends needing any database preparation
        connection.prepare_database()

        # Get the django_migrations table wrapper
        recorder = MigrationRecorder(connection)

        # Store existing state
        ordered_state = recorder.migration_qs.values_list('app', 'name').order_by('applied')

        # Truncate the table
        recorder.flush()
        self.stdout.write('Migration history reset.')
        self.stdout.write('Remember to run "python manage.py migrate --fake --fake-initial')
