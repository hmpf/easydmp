from django import forms

from easydmp.dmpt.forms import AbstractNodeFormSet
from easydmp.dmpt.models.questions.mixins import SaveMixin, NoCheckMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.utils import get_question_type_from_filename

__all__ = [
    'MultistringQuestion',
    'MultistringFormSet',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'MultistringQuestion'


class MultistringQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question answerable with one or more strings
    """
    TYPE = TYPE

    class Meta:
        proxy = True
        managed = False

    def get_canned_answer(self, choices, frame=True, **kwargs):
        if not choices:
            return self.get_optional_canned_answer()
        if len(choices) == 1:
            return self.frame_canned_answer(choices[0], frame)
        result = '{} and {}'.format(', '.join(choices[:-1]), choices[-1])
        return self.frame_canned_answer(result, frame)

    def pprint(self, value):
        choices = value['choice']
        if len(choices) < 2:  # Single line or fixed optional line
            return self.get_canned_answer(value)

        lines = list()
        for choice in choices:
            lines.append(f'* {choice}')
        textblob = '\n'.join(lines) + '\n'
        return self.frame_canned_answer(textblob, frame=False)

    def pprint_html(self, value):
        choices = value['choice']
        if len(choices) < 2:  # Single line or fixed optional line
            return self.get_canned_answer(choices)

        lines = list()
        for choice in choices:
            lines.append(f'<li>{choice}</li>')
        htmlblob = '\n'.join(lines)
        result = f'<ul>\n{htmlblob}\n</ul>'
        return self.frame_canned_answer(htmlblob, frame=False)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            if choice and isinstance(choice, str):
                return True
        return False


class MultistringFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    MAX_LENGTH = 255
    choice = forms.CharField(
        label='',  # Hide the label from crispy forms
        max_length=MAX_LENGTH,
    )


class AbstractMultistringFormSet(AbstractNodeFormSet):
    FORM = MultistringFormSetForm
    required = ['string']

    @classmethod
    def generate_choice(cls, choice):
        return choice

    def serialize_subform(self):
        json_schema = {
            'properties': {
                'string': {
                    'type': 'string',
                },
            },
        }
        return self._set_required_on_serialized_subform(json_schema)


MultistringFormSet = AbstractMultistringFormSet.generate_formset()
Question.register_form_class(TYPE, MultistringFormSet)
