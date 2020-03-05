from django.core.management.base import BaseCommand, CommandError, CommandParser

from easydmp.plan.utils import select_plans


class Command(BaseCommand):
    help = "Analyze which plans have answered which questions"

    def add_arguments(self, parser):
        parser.add_argument('-s', '--section', nargs='+', type=int, default=[],
                            help='Sections to analyze (id)')
        parser.add_argument('-t', '--template', nargs='+', type=int, default=[],
                                 help='Templates to analyze (id)')
        parser.add_argument('-p', '--plan', nargs='+', type=int, default=[],
                                 help='Plans to analyze (id)')

    def handle(self, *args, **options):
        plan_ids = options['plan'] or ()
        template_ids = options['template'] or ()
        section_ids = options['section'] or ()

        plan_qs, template_qs, section_qs = select_plans(
            plan_ids, template_ids, section_ids
        )

        if not plan_qs:
            self.stderr.write('No plans match all criteria, aborting')
            return

        section_ids = [s.id for s in section_qs]
        empty = True
        for plan in plan_qs:
            report = []
            report.append('{} ({}), total answers: {}'.format(
                plan.title, plan.id, len(plan.data.keys()))
            )
            answered_in_section = None
            answer_ids = set([int(key) for key in plan.data.keys()])
            for section in plan.template.sections.filter(id__in=section_ids):
                question_ids = section.questions.values_list('id', flat=True)
                answered_in_section = set(tuple(question_ids)) & answer_ids
                report.append(
                    '\tSection has {} questions'.format(question_ids.count())
                )
                report.append('\tAnswered in section {} ({}): {}'.format(
                    section.position, section.id, answered_in_section
                ))
            if not answered_in_section:
                continue
            empty = False
            self.stdout.write('\n'.join(report))
            self.stdout.write('')

        if empty:
            self.stderr.write('No answers match all criteria, nothing to do')
