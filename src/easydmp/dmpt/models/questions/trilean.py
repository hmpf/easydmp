from django import forms

from easydmp.dmpt.forms import AbstractNodeForm
from easydmp.dmpt.models.questions.mixins import ChoiceValidationMixin
from easydmp.dmpt.models.questions.mixins import SaveMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.utils import get_question_type_from_filename

__all__ = [
    'TrileanQuestion',
    'TrileanForm',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'TrileanQuestion'


class TrileanQuestion(ChoiceValidationMixin, SaveMixin, Question):
    """A branch-capable question answerable with "Yes", "No" or "Unknown"
    """
    TYPE = TYPE

    class Meta:
        proxy = True
        managed = False

    def is_valid(self):
        canned_answers = self.canned_answers.values_list('choice', flat=True)
        if set(canned_answers) == set(('Yes', 'No', 'Unknown')):
            return True
        return False

    def _serialize_condition(self, answer):
        if str(answer).lower() in ('true', 'yes', 'on'):
            return 'Yes'
        if str(answer).lower() in ('false', 'no', 'off'):
            return 'No'
        return 'Unknown'

    def get_choices(self):
        choices = (
            ('Yes', 'Yes'),
            ('No', 'No'),
            ('Unknown', 'Unknown'),
        )
        return choices


class TrileanForm(AbstractNodeForm):
    TYPE = TYPE
    json_type = 'string'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.RadioSelect,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})
