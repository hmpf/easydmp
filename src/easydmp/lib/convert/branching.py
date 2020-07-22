import logging

from easydmp.dmpt.models import ExplicitBranch, Section, Question


LOG = logging.getLogger(__name__)


try:
    from flow.models import Edge, Node, FSA
except ImportError:
    # The old 'flow' app has been removed
    def cleanup_empty_flow(_):
        pass
else:
    def cleanup_empty_flow(dryrun=True):
        result = {}

        edges = Edge.objects.filter(prev_node=None, next_node=None)
        result['edges'] = {'found': edges.count(), 'deleted': 0}

        nodes = Node.objects.filter(prev_nodes=None, next_nodes=None)
        result['nodes'] = {'found': nodes.count(), 'deleted': 0}

        used_nodes = Node.objects.filter(payload__isnull=False)
        unused_fsas = FSA.objects.exclude(nodes__in=used_nodes)
        fsas = FSA.objects.filter(nodes=None) & unused_fsas
        result['fsas'] = {'found': fsas.count(), 'deleted': 0}

        if dryrun is False:
            edges_deleted = edges.delete()
            result['edges']['deleted'] = edges_deleted
            nodes_deleted = nodes.delete()
            result['nodes']['deleted'] = nodes_deleted
            fsas_deleted = fsas.delete()
            result['fsas']['deleted'] = fsas_deleted

        return result


def get_sections_that_need_converting():
    sections = Section.objects.filter(branching=True)
    oldstyle_section_ids = []
    for section in sections:
        if section.questions.filter(node__isnull=False).exists():
            oldstyle_section_ids.append(section.id)
            continue
    return Section.objects.filter(id__in=oldstyle_section_ids)


def copy_from_FSA_models_to_ExplicitBranch(question):
    next_questions = question.get_potential_next_questions_with_transitions()
    LOG.debug("Handling %s, new", question.id)
    for trn in next_questions:
        category, condition, next_question = trn.category, trn.choice, trn.next
        if next_question and next_question.position == question.position + 1:
            # Adjacent! Use 'position'
            LOG.debug("\tSkipped transition, adjacent by position")
            continue
        next_id = getattr(next_question, 'id', None)
        LOG.debug("Transition (%s, %s, %s)", category, condition, next_id)
        if category in ('position', 'Node-edgeless'):
            LOG.debug("\tSkipped transition, made irrelevant")
            continue
        if category == 'last':
            if question == question.section.last_question:
                # Implicit last, don't save
                continue
            category = 'Last'
            condition = ''
            next_question = None
        elif category == 'Edge':
            category = 'ExplicitBranch'
        if category == 'ExplicitBranch' and next_question is None:
            category = 'Last'
        kwargs = {
            'current_question': question,
            'next_question': next_question,
            'category': category,
            'condition': condition,
        }
        eb = ExplicitBranch.objects.create(**kwargs)
        LOG.debug("\tCreated %s", eb)
        if category in ('CannedAnswer', 'ExplicitBranch'):
            for ca in question.canned_answers.all():
                if ca.choice == condition:
                    ca.transition = eb
                    ca.save()
                    LOG.debug("Altered CA %s", ca)


def clean_converted_sections(sections):
    for section in sections:
        for question in section.questions.filter(node__isnull=False):
            question.node = None
            question.save()
            LOG.debug("Removed node from question \"{}\"".format(question))
            cas = question.canned_answers.filter(edge__isnull=False)
            cas.update(edge=None)
            LOG.debug("""Removed edges from question"""
                      """ "{}"'s CannedAnswers""".format(question))


def convert_branching(sections, File, verbosity=0, clean=False):
    for section in sections:
        section.renumber_positions()
        if verbosity > 1:
            File.write('Renumbered questions in sections to avoid gaps')
    for question in (Question.objects
                     .filter(section__in=sections)
                     .order_by('section__template__id',
                               'section__position',
                               'position')
                     ):
        copy_from_FSA_models_to_ExplicitBranch(question)
    if clean:
        clean_converted_sections(sections)
