from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Section
from easydmp.dmpt.models import Template
from easydmp.lib.convert.branching import cleanup_empty_flow
from easydmp.lib.convert.branching import convert_branching
from easydmp.lib.convert.branching import get_sections_that_need_converting


class Command(BaseCommand):
    help = 'Migrates branching templates from the old to the new way'

    def add_arguments(self, parser):
        command_group = parser.add_mutually_exclusive_group(required=True)
        command_group.add_argument(
            '-t', '--templates', nargs='*', type=int, default=[],
            help='Migrate the specific section id\'s'
        )
        command_group.add_argument(
            '-s', '--sections', nargs='*', type=int, default=[],
            help='Migrate the specific template id\'s'
        )
        command_group.add_argument(
            '-a', '--all', action='store_true',
            help='Migrate all templates'
        )
        command_group.add_argument(
            '-l', '--list', action='store_true',
            help='Show which templates and sections need converting'
        )
        command_group.add_argument(
            '-c', '--clean', action='store_true',
            help='Clean up unused fsas, nodes and edges'
        )
        parser.add_argument(
            '-p', '--purge', action='store_true',
            help='Remove usage of old flow: fsas, nodes and edges'
        )
        parser.add_argument(
            '-n', '--dryrun', action='store_true',
            help='Dryrun'
        )

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        dryrun = options['dryrun']
        purge = options['purge']

        if options['list']:
            sections = get_sections_that_need_converting()
            for section in sections.order_by('template_id','position'):
                self.stdout.write('Template "{}" ({}): "{}" ({})'.format(
                    section.template, section.template.id, section, section.id
                ))
            return

        if options['clean']:
            cleanup_result = cleanup_empty_flow(dryrun=dryrun)
            if cleanup_result and verbosity >= 2:
                self.stdout.write('\nRemoving stale FSAs..')
                for model, result in cleanup_result.items():
                    found = result['found']
                    deleted = result['deleted']
                    self.stdout.write(
                        'Found {} {}, deleted {}'.format(found, model, deleted)
                    )
                self.stdout.write('')
            return

        templates = Template.objects.all()
        if options['templates']:
            templates = Template.objects.filter(pk__in=options['templates'])
        sections = Section.objects.filter(template__in=templates)
        if options['sections']:
            sections = Section.objects.filter(pk__in=options['sections'])
        sections = sections.filter(branching=True)
        convert_branching(sections, self.stdout, verbosity, purge)
