import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from easydmp.rdadcs.lib.importing import ImportRDA10
from easydmp.rdadcs.lib.importing import RDADCSImportError


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument('owner', help='Username of the person importing')

    def handle(self, *args, **options):
        if options['verbosity'] in (0, 1):
            logging.disable(logging.ERROR)
        elif options['verbosity'] > 2:
            logging.disable(logging.CRITICAL)
        filename = options['filename']
        owner_username = options['owner']
        User = get_user_model()
        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist:
            self.stderr.write(f'A record for user {owner_username} does not exist, aborting')
            return
        with open(filename, 'r') as FILE:
            jsonblob = json.load(FILE)
        importer = ImportRDA10(jsonblob, owner, via='CLI')
        try:
            importer.import_rdadcs()
        except RDADCSImportError as e:
            self.stderr.write(str(e))
        logging.disable(logging.NOTSET)
