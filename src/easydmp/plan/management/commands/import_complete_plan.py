import argparse
import json
import sys
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from easydmp.plan.import_plan import (
    deserialize_plan_export,
    import_serialized_plan_export,
    PlanImportError
)


class Command(BaseCommand):
    help = "Import a plan and all its dependencies from a json dump"

    def add_arguments(self, parser):
        parser.add_argument('username', type=str,
                            help='Username of user that imports the plan')
        parser.add_argument('filename', nargs='?', default=sys.stdin,
                            type=argparse.FileType('rb'),
                            help='Read from FILE, default: stdin')

    def handle(self, *args, **options):
        username = options['username']
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            error_msg = f'User "{username} does not exist, halting import'
            sys.stderr.write(error_msg)
            sys.exit(1)

        filename = options['filename'] or None
        raw_blob = filename.read()
        filename.close()

        try:
            serialized_dict = deserialize_plan_export(raw_blob)
        except PlanImportError as e:
            self.stderr.write(f"{e}, cannot import")
            sys.exit(1)
        try:
            pim = import_serialized_plan_export(serialized_dict, user)
        except PlanImportError as e:
            self.stderr.write(str(e))
            sys.exit(1)
        else:
            self.stdout.write(f'Successfully imported "{pim.plan}", id #{pim.plan.id}')
