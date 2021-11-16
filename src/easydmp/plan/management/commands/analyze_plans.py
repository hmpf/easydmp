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

        self.stdout.write('To analyze:')
        self.stdout.write(f'\t{plan_qs.count()} plans')
        if template_qs.exists():
            self.stdout.write(f'\t{template_qs.count()} templates')
        if section_qs.exists():
            self.stdout.write(f'\t{section_qs.count()} sections')
        self.stdout.write()

        section_ids = [s.id for s in section_qs]
        empty = True
        for plan in plan_qs:
            report = []
            answers = []
            total_answers = plan.num_total_answers
            report.append('{} ({}), total answers: {}'.format(
                plan.title, plan.id, total_answers)
            )
            answered_in_answerset = None
            for section in (
                    plan.template.sections
                    .order_by('position').filter(id__in=section_ids)
                ):
                question_ids = section.questions.values_list('id', flat=True)
                report.append(
                    f'\tSection {section.position} ({section.id}) has '
                    f'{question_ids.count()} questions'
                )
                for answerset in plan.answersets.filter(section=section):
                    answer_ids = set(map(int, answerset.data.keys()))
                    answered_in_answerset = set(tuple(question_ids)) & answer_ids
                    report.append('\tAnswerset "{}": {}'.format(
                        answerset.identifier,
                        answered_in_answerset
                    ))
                    report.append('')
                if not answered_in_answerset:
                    continue
                empty = False
                report.append('')
            self.stdout.write('\n'.join(report))
            self.stdout.write('')

        if empty:
            self.stderr.write('No answers match all criteria, nothing to do')
