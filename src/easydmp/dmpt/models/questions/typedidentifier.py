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
    'TypedIdentifierQuestion',
    'TypedIdentifierForm',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'TypedIdentifierQuestion'


class TypedIdentifierQuestion(SaveMixin, Question):
    """A non-branch-capable question answerable with an identifier and its type

    Fields in the choice:
        identifier: a string
        type: a string
    """
    TYPE = TYPE

    class Meta:
        proxy = True
        managed = False

    def is_valid(self):
        if self.canned_answers.count() > 1:
            return True
        return False

    def pprint(self, value):
        identifier = value['choice']['identifier']
        type_ = value['choice']['type']
        return f'{identifier} ({type_})'

    def validate_choice(self, data: Data) -> bool:
        answer = data.get('choice', NotSet) or NotSet
        if answer is NotSet:
            if self.optional:
                return True
            return False
        if answer.get('identifier', None) and answer.get('type', None):
            if answer['type'] in self.get_choices_keys():
                return True
        return False

    def get_choices(self):
        # ignores CannedAnswer.canned_text
        choices = tuple(self.canned_answers.order().values_list('choice', 'choice'))
        return choices

    def get_identifier(self, answer):
        return answer['identifier']


class TypedIdentifierWidget(forms.MultiWidget):
    template_name = f'widgets/{TYPE}_widget.html'

    def __init__(self, attrs=None, *args, **kwargs):
        widgets = [
            forms.TextInput(attrs=attrs),
            forms.Select(attrs=attrs),
        ]
        self.widgets = widgets
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            identifier, type_ = value['identifier'], value['type']
            return identifier, type_
        return (None, None)


class TypedIdentifierField(forms.MultiValueField):

    def __init__(self, choices=None, *args, **kwargs):
        assert choices, 'No types given'
        kwargs['widget'] = TypedIdentifierWidget
        kwargs['require_all_fields'] = True
        fields = [
            forms.CharField(required=True),
            forms.ChoiceField(required=True, choices=choices),
        ]
        super().__init__(fields, *args, **kwargs)
        self.widget.widgets[1].choices = self.fields[1].widget.choices

    def compress(self, value):
        return {'identifier': value[0], 'type': value[1]}


class TypedIdentifierForm(AbstractNodeForm):
    TYPE = TYPE
    json_type = 'object'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = TypedIdentifierField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['properties'] = {
            'identifier': {'type': 'string'},
            'type': {'type': 'string'}
        }
        attrs['required'] = ['identifier', 'type']
        return attrs
