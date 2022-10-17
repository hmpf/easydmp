import logging

from easydmp.constants import NotSet

from ..base import Question
from ..base import QuestionType
from ...typing import AnswerChoice

from easydmp.eestore.models import EEStoreCache

__all__ = [
    'NoCheckMixin',
    'PrimitiveTypeMixin',
    'SimpleFramingTextMixin',
    'PrimitiveTypeMixin',
    'ChoiceValidationMixin',
    'IsSetValidationMixin',
    'NotListedMixin',
    'SaveMixin',
    'EEStoreMixin',
]

LOG = logging.getLogger(__name__)

# models, querysets, managers


class NoCheckMixin:

    def is_valid(self):
        return True


class SimpleFramingTextMixin:
    """Generate a canned answer for a non-branching, atomic type

    This includes strings, but excludes any other iterables.
    """
    def get_canned_answer(self, choice: AnswerChoice, frame=True, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()  # type: ignore

        choice = str(choice)
        return self.frame_canned_answer(choice, frame)  # type: ignore


class PrimitiveTypeMixin(NoCheckMixin, SimpleFramingTextMixin):
    pass


class ChoiceValidationMixin:

    def validate_choice(self, data):
        choice = data.get('choice', None)
        if self.optional and not choice:
            return True
        if choice in self.get_choices_keys():
            return True
        return False


class IsSetValidationMixin:

    def validate_choice(self, data):
        choice = data.get('choice', NotSet) or NotSet
        if choice is NotSet:
            if self.optional:
                return True
            return False
        if choice:
            return True
        return False


class NotListedMixin:

    def _serialize_condition(self, answer):
        choice = answer.get('choice', {})
        return choice.get('not-listed', False)

    def get_transition_choice(self, answer):
        choice = answer.get('choice', None)
        if choice is None:
            return None
        if choice['not-listed']:
            return 'not-listed'
        return 'False'


class SaveMixin:

    def save(self, *args, **kwargs):
        if not self.input_type_id == self.TYPE:
            qt, _ = QuestionType.objects.get_or_create(id=self.TYPE)
            self.input_type = qt
        if self.has_notes is None:
            self.has_notes = self.input_type.allow_notes
        super().save(*args, **kwargs)


class EEStoreMixin:

    def is_valid(self):
        if self.eestore:
            return True
        return False

    def get_entries(self, eestore_pids):
        all_entries = self.eestore.get_cached_entries()
        entries = all_entries.filter(eestore_pid__in=eestore_pids)
        return entries

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        return self.get_canned_answer(value['choice'], frame=False)

    def get_choices(self):
        if self.eestore.sources.exists():
            sources = self.eestore.sources.all()
        else:
            sources = self.eestore.eestore_type.sources.all()
        qs = EEStoreCache.objects.filter(source__in=sources)
        choices = qs.values_list('eestore_pid', 'name')
        return choices
