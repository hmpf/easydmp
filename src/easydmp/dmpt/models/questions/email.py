from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django import forms

from easydmp.constants import NotSet
from easydmp.dmpt.forms import AbstractNodeForm
from easydmp.dmpt.models.questions.mixins import IsSetValidationMixin, PrimitiveTypeMixin, SaveMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.typing import Data
from easydmp.dmpt.utils import get_question_type_from_filename

__all__ = [
    'EmailQuestion',
    'EmailForm',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'EmailQuestion'


class EmailQuestion(PrimitiveTypeMixin, SaveMixin, Question):
    "A non-branch-capable question answerable with an email address"
    TYPE = TYPE

    class Meta:
        proxy = True
        managed = False

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet)
        breakpoint()
        if self.optional and answer is NotSet:
            return True
        answer = answer.strip()
        try:
            value = validate_email(answer)
        except ValidationError:
            return False
        return True


class EmailForm(AbstractNodeForm):
    TYPE = TYPE
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.EmailField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['format'] = 'email'  # idn-email not supported currently
        return attrs
