from importlib import import_module as _import_module
from pathlib import Path as _Path # Hide it from star-imports

from django.utils.module_loading import import_string as _import_string

from .base import (
    CannedAnswer,
    ExplicitBranch,
    Question,
    QuestionType,
    Section,
    Template,
    TemplateGroupObjectPermission,
    TemplateImportMetadata,
    TemplateQuerySet,
    TemplateUserObjectPermission,
)
from .questions import (
    BooleanQuestion,
    ChoiceQuestion,
    DateQuestion,
    DateRangeQuestion,
    ExternalChoiceNotListedQuestion,
    ExternalChoiceQuestion,
    ExternalMultipleChoiceNotListedOneTextQuestion,
    ExternalMultipleChoiceOneTextQuestion,
    MultiNamedURLOneTextQuestion,
    MultipleChoiceOneTextQuestion,
    NamedURLQuestion,
    PositiveIntegerQuestion,
    ReasonQuestion,
    ShortFreetextQuestion,
)


def _get_single_file_questiontypes(path, *exclude):
    questiondir = _Path(path)
    exclude = set(exclude)
    standalone_question_types = []
    for child in questiondir.iterdir():
        # Skip __init__.py and excluded files
        if not child or child.name[0] in ('_', '.') or child.name in exclude:
            continue
        filename = child.stem.strip()
        if filename:
            standalone_question_types.append(filename)
    return standalone_question_types


def _import_local_standalone_question_types(types):
    for qtype in types:
        module_name = f'{__name__}.questions.{qtype}'
        question_class_pointer = f'{module_name}.QUESTION_CLASS'
        try:
            question_class_name = _import_string(question_class_pointer)
        except ImportError:
            continue
        dotted_path = f'{module_name}.{question_class_name}'
        try:
            question_class = _import_string(dotted_path)
        except ImportError:
            continue
        globals()[question_class_name] = question_class


_local_standalone_question_types = _get_single_file_questiontypes(
    _Path(__file__).parents[0]  / 'questions',
    'mixins.py',
)
_import_local_standalone_question_types(_local_standalone_question_types)
