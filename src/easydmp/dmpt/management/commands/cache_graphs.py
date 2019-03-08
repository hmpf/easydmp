from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Section


class Command(BaseCommand):
    help = "Write out section graphs to on-disk cache"
    formats = ['pdf', 'svg', 'png', 'dot']

    def add_arguments(self, parser):
        format_parser = parser.add_mutually_exclusive_group(required=True)
        format_parser.add_argument('-f', '--formats', nargs='+', type=str, default=[],
                                   help='Cache the specific format',
                                   choices=self.formats)
        format_parser.add_argument('-F', '--all-formats', action='store_const',
                                   help='Cache all formats',
                                   const=self.formats,
                                   dest='formats',
                                   )
        template_parser = parser.add_mutually_exclusive_group(required=True)
        template_parser.add_argument('templates', nargs='*', type=int, default=[],
                                     help='Cache the specific template (id)')
        template_parser.add_argument('-A', '--all-templates', action='store_true',
                                    help='Cache all templates',
                                    dest='all_templates',
                                    )

    def handle(self, *args, **options):
        formats = options['formats']
        templates = options['templates']

        if options['all_templates']:
            sections = Section.objects.all()
        else:
            sections = Section.objects.filter(template__id__in=options['templates'])

        for format in formats:
            for s in sections:
                s.refresh_cached_dotsource(format)
