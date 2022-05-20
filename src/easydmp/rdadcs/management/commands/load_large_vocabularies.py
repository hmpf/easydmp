from django.core.management.base import BaseCommand, CommandError

from easydmp.eestore.utils import fill_cache_from_class
import easydmp.rdadcs.data.large_controlled_vocabularies as lcv


class Command(BaseCommand):
    help = "Load EEStore cache with language, country, currency code"

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        classes = [cls for cls in map(lcv.__dict__.get, lcv.__all__)]
        for cls in classes:
            source = fill_cache_from_class(cls)
            if verbosity:
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully created {source} from class'
                ))
