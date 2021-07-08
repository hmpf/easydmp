# Generated by Django 3.2.3 on 2021-07-12 10:22

from collections import defaultdict

from django.db import migrations
from django.db.models import Q


def make_mapping(templates):
    # Reverse lookups doesn't work in migrations
    lookup = (
        Question.objects
        .select_related('section')
        .filter(section__template__in=templates)
        .only('section__template', 'section', 'id')
        .order_by('section__template_id', 'section_id', 'id')
        .values_list('section__template_id', 'section_id', 'id')
    )
    mapping = defaultdict(dict)
    for tid, sid, qid in lookup:
        mapping[tid].setdefault(sid, {})
        mapping[tid][sid][str(qid)] = None
    return mapping


def migrate_answers_to_answerset(apps, schema_editor):
    global AnswerSet
    AnswerSet = apps.get_model('plan', 'AnswerSet')
    Plan = apps.get_model('plan', 'Plan')
    global Question
    Question = apps.get_model('dmpt', 'Question')
    plans = Plan.objects.filter(Q(data__isnull=False) | Q(previous_data__isnull=False)).distinct()
    templates = plans.values_list('template', flat=True)
    mapping = make_mapping(templates)
    for plan in plans:
        move_answers_to_answerset(plan, mapping)


def move_answers_to_answerset(plan, mapping):
    if not (plan.data or plan.previous_data):
        return
    for sid, qids in mapping[plan.template.id].items():
        # Ensure at least one answerset
        answerset, _ = AnswerSet.objects.get_or_create(plan=plan, section_id=sid)
        for qid in qids:
            if qid in plan.data:
                answerset.data[qid] = plan.data[qid]
            if qid in plan.previous_data:
                answerset.previous_data[qid] = plan.previous_data[qid]
        # We cannot validate in a migration (no non-standard model-methods
        # available) so do a poor mans validation and trust the plan
        if plan.valid:
            answerset.valid = True
        answerset.save()
    plan.data = {}
    plan.previous_data = {}
    plan.save(update_fields=['data', 'previous_data'])


def migrate_answers_to_plan(apps, schema_editor):
    AnswerSet = apps.get_model('plan', 'AnswerSet')
    Plan = apps.get_model('plan', 'Plan')
    for plan in Plan.objects.all():
        answerset = AnswerSet.objects.filter(plan=plan).order_by('id').first()
        plan.data.update(**answerset.data)
        plan.previous_data.update(**answerset.previous_data)
        plan.save(update_fields=['data', 'previous_data'])
        answerset.data = {}
        answerset.previous_data = {}
        answerset.save(update_fields=['data', 'previous_data'])


class Migration(migrations.Migration):

    dependencies = [
        ('plan', '0013_link_missing_answersets'),
        ('dmpt', '0008_switch_to_native_JSONField'),
    ]

    operations = [
        migrations.RunPython(migrate_answers_to_answerset, migrate_answers_to_plan),
    ]
