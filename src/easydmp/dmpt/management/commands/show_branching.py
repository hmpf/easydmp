from django.core.management.base import BaseCommand, CommandError

from easydmp.dmpt.models import Template


class Command(BaseCommand):
    help = "List sections (and templates) that branches"

    def handle(self, *args, **options):
        templates = Template.objects.filter(sections__branching=True).distinct()
        for template in templates.order_by('id'):
            sections = template.sections.filter(branching=True)
            self.stdout.write('Template "{}" ({}):'.format(
                template, template.id
            ))
            for section in sections.order_by('position'):
                self.stdout.write('\t"{}" ({}), {} questions'.format(
                    section, section.id, section.questions.count()
                ))
