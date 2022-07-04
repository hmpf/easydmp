from easydmp.dmpt.models import Question, QuestionType
from easydmp.dmpt.models import Section
from ..models import RDADCSKey, RDADCSQuestionLink, RDADCSSectionLink


def createupdate_rdakey(path, input_type):
    warnings = []
    if not input_type:
        warnings.append(f'Path {path} lacks a type')
    questiontypes = {qt.id: qt for qt in QuestionType.objects.all()}
    qt = None
    if input_type:
        try:
            qt = QuestionType.objects.get(id=input_type)
        except QuestionType.DoesNotExist:
            warnings.append(f'Path {path} has unknown type: {input_type}')
    # Avoid *_or_create because pk is not an AutoField
    slug = RDADCSKey.slugify_path(path)
    try:
        key = RDADCSKey.objects.get(slug=slug)
    except RDADCSKey.DoesNotExist:
        RDADCSKey.objects.create(slug=slug, path=path, input_type=qt)
    else:
        if qt and key.input_type != qt:
            key.input_type = qt
            key.save()
    return warnings


def createupdate_link(path, pk, dmpt_model, link_model, fieldname):
    try:
        rdakey = RDADCSKey.objects.get(path=path)
    except RDADCSKey.DoesNotExist:
        raise ValueError(f"No key with path {path} exists")
    try:
        obj = dmpt_model.objects.get(pk=pk)
    except dmpt_model.DoesNotExist:
        raise ValueError(f"No instance with id {pk} exists")
    # Avoid *_or_create because pk is not an AutoField
    kwarg = {fieldname: pk}
    try:
        rl = link_model.objects.get(**kwarg)
    except link_model.DoesNotExist:
        link_model.objects.create(key=rdakey, **kwarg)
    else:
        if rl.key.path != path:
            rl.key = rdakey
            rl.save()


def createupdate_rda_question_link(path, pk):
    return createupdate_link(path, pk, Question, RDADCSQuestionLink, 'question_id')


def createupdate_rda_section_link(path, pk):
    return createupdate_link(path, pk, Section, RDADCSSectionLink, 'section_id')
