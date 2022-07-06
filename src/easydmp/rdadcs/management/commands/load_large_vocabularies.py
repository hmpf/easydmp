from django.core.management.base import BaseCommand, CommandError

from easydmp.rdadcs.lib.resources import load_rdadcs_eestore_cache_modelresource


class Command(BaseCommand):
    help = "Load EEStore cache with language, country, currency code"

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        for source in load_rdadcs_eestore_cache_modelresource():
            if verbosity:
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully created {source} from class'
                ))
