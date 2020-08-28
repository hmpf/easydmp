from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Section


class Command(BaseCommand):
    help = "Write out section graphs to file"
    formats = ['pdf', 'svg', 'png', 'dot']

    def add_arguments(self, parser):
        parser.add_argument('-d', '--debug',  action='store_true',
                            help='Add debug info to graph')
        format_parser = parser.add_mutually_exclusive_group(required=True)
        format_parser.add_argument('-f', '--formats', nargs='+', type=str, default=[],
                                   help='Use the specific format',
                                   choices=self.formats)
        format_parser.add_argument('-F', '--all-formats', action='store_const',
                                   help='Use all formats',
                                   const=self.formats,
                                   dest='formats',
                                   )
        template_parser = parser.add_mutually_exclusive_group(required=True)
        template_parser.add_argument('-s', '--sections', nargs='+', type=int, default=[],
                                     help='Generate for the specific section (id)')
        template_parser.add_argument('-t', '--templates', nargs='+', type=int, default=[],
                                     help='Generate for the specific template (id)')
        template_parser.add_argument('-A', '--all-templates', action='store_true',
                                    help='Generate for all sections',
                                    dest='all_sections',
                                    )

    def handle(self, *args, **options):
        formats = options['formats']
        section_ids = options['sections']
        template_ids = options['templates']
        debug = options['debug']

        if options['all_sections']:
            sections = Section.objects.all()
        elif section_ids:
            sections = Section.objects.filter(id__in=section_ids)
        elif template_ids:
            sections = Section.objects.filter(template__id__in=template_ids)
        else:
            # raise error
            return

        root_directory = '.'
        for format in formats:
            for s in sections:
                filename = s.get_dotsource_filename()
                s.render_dotsource_to_file(format, filename, root_directory=root_directory, debug=debug)
