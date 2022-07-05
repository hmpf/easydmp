from datetime import datetime

from django import forms

from easydmp.constants import NotSet
from easydmp.dmpt.forms import AbstractNodeForm
from easydmp.dmpt.models.questions.mixins import PrimitiveTypeMixin
from easydmp.dmpt.models.questions.mixins import SaveMixin
from easydmp.dmpt.models.base import Question
from ...typing import Data
from easydmp.dmpt.utils import get_question_type_from_filename

__all__ = [
    'DateTimeQuestion',
    'DateTimeForm',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'DateTimeQuestion'


class DateTimeQuestion(PrimitiveTypeMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with an iso datetime

    Stored format: "YYYY-mm-ddThh:mm:ssZ"
    """
    TYPE = TYPE

    class Meta:
        proxy = True
        managed = False

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        if not answer:
            answer = NotSet
        if self.optional and answer is NotSet:
            return True

        try:
            # python's vanilla fromisoformat is not up to spec
            if answer[-1] in ('z', 'Z'):
                answer = answer[:-1] + '+00:00'
            datetime.fromisoformat(answer)
            return True
        except (TypeError, ValueError):
            return False


class DateTimeForm(AbstractNodeForm):
    TYPE = TYPE
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.DateTimeField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['format'] = 'date-time'
        return attrs
