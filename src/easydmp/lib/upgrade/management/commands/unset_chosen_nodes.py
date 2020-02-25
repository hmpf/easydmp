from django.core.management.base import BaseCommand, CommandError, CommandParser

from easydmp.dmpt.models import Section, Template


class Command(BaseCommand):
    help = "Unset nodes on questions"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-a', '--all', action='store_true', default=False,
                            help='Unset all nodes')
        group.add_argument('-s', '--section', nargs='+', type=int, default=[],
                            help='Only unset nodes in the specific section (id)',)
        group.add_argument('-t', '--template', nargs='+', type=int, default=[],
                                help='Only unset nodes in the specfic template (id)',)


    def handle(self, *args, **options):
        section_qs = Section.objects.filter(branching=True)
        sections = None
        if options['all']:  # Explicit better than implicit
            sections = section_qs
        elif options['section']:
            sections = section_qs.filter(id__in=options['section'])
        elif options['template']:
            sections = section_qs.filter(template_id__in=options['template'])
        else:
            self.stderr.write('Nothing chosen, nothing done')
            return

        nodes_unset = 0
        for s in sections:
            for q in s.questions.all():
                if not q.node:
                    continue
                nodes_unset += 1
                self.stdout.write('Unsetting {} on {}, section {}'.format(
                    q.node, q, s))
                q.node = None
                q.save()
        self.stdout.write('Unset {} nodes'.format(nodes_unset))
