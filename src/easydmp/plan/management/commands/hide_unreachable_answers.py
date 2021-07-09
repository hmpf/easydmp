from django.core.management.base import BaseCommand, CommandError, CommandParser

from easydmp.dmpt.models import Section
from easydmp.plan.models import Plan
from easydmp.plan.utils import select_plans


class Command(BaseCommand):
    help = "Hide unreachable answers in plans with branching templates"

    def add_arguments(self, parser):
        cmd = self
        subparsers = parser.add_subparsers(
            title='Subcommands',
            help='foo',
            required=True,
            dest="subcommand",
            parser_class=lambda **kw: CommandParser(**kw)
        )
        all_parser = subparsers.add_parser('all', help='Hide all unreachable answers everywhere')
        pick_parser = subparsers.add_parser('pick', help='Select a subset of plans or part of a plan to hide answers in')
        pick_parser.add_argument('-s', '--section', nargs='+', type=int, default=[],
                            help='Only hide answers in the specific section (id)',)
        pick_parser.add_argument('-t', '--template', nargs='+', type=int, default=[],
                                 help='Only hide answers from plans using the specfic template (id)',)
        pick_parser.add_argument('-p', '--plan', nargs='+', type=int, default=[],
                                 help='Only hide answers from the specific plans (id)',)

    def handle(self, *args, **options):
        section_qs = None
        plan_qs = Plan.objects.exclude(data={})
        if options['subcommand'] == 'pick':
            plan_ids = options['plan'] or ()
            template_ids = options['template'] or ()
            section_ids = options['section'] or ()
            if not (any(plan_ids) or any(template_ids) or any(section_ids)):
                self.stderr.write('No criteria given, aborting')
                return

            plan_qs, _, section_qs = select_plans(plan_ids, template_ids,
                                                  section_ids)

            if not plan_qs:
                self.stderr.write('No plans match all criteria, aborting')
                return

        for plan in plan_qs:
            total_answers = plan.num_total_answers
            self.stdout.write(f'{plan.title} ({plan.id}), answers: {total_answers}')
            changed = plan.hide_unreachable_answers(section_qs=section_qs)
            if not changed:
                self.stdout.write(f'{plan.title} ({plan.id}) not touched')
            else:
                self.stdout.write(f'{plan.title} ({plan.id}) CHANGED')
            self.stdout.write('')
