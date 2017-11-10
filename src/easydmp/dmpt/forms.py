from datetime import date

from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import Template
from .fields import DateRangeField


class TemplateForm(forms.ModelForm):
    template_type = forms.ModelChoiceField(queryset=Template.objects.exclude(published=None))

    class Meta:
        model = Template
        fields = ['title']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))


class DeleteForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Yes, really delete'))


class AbstractNodeForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.question_pk = kwargs.pop('question')
        self.label = kwargs.pop('label')
        self.help_text = getattr(self.question_pk, 'help_text', '')
        self.choices = kwargs.pop('choices', None)
        self.has_prevquestion = kwargs.pop('has_prevquestion', False)
        kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)

        self._add_choice_field()
        self._add_notes_field()

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-{}'.format(self.question_pk)
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        if self.has_prevquestion:
            self.helper.add_input(Submit('prev', 'Prev'))
        self.helper.add_input(Submit('submit', 'Next'))

    def _add_choice_field(self):
        pass

    def _add_notes_field(self):
        notes = forms.CharField(required=False, widget=forms.Textarea)
        self.fields['notes'] = notes

    def serialize(self):
        return {
            'choice': self.cleaned_data['choice'],
            'notes': self.cleaned_data.get('notes', ''),
        }

    def pprint(self):
        if self.is_valid():
            return self.cleaned_data['choice']
        return 'Not set'


class BooleanForm(AbstractNodeForm):

    def _add_choice_field(self):
        choices = (
            (True, 'Yes'),
            (False, 'No'),
        )
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.RadioSelect,
        )

    def pprint(self):
        if self.is_valid():
            return 'Yes' if self.cleaned_data['choice'] else 'No'
        return 'Not set'

    def serialize(self):
        out = {
            'notes': self.cleaned_data.get('notes', ''),
            'choice': None,
        }
        if self.is_valid():
            data = self.cleaned_data['choice']
            if data == 'True':
                out['choice'] = True
            if data == 'False':
                out['choice'] = False
            return out
        return {}

class ChoiceForm(AbstractNodeForm):

    def _add_choice_field(self):
        choices = [(k, k) for k in self.choices]
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.RadioSelect,
        )


class MultipleChoiceOneTextForm(AbstractNodeForm):

    def _add_choice_field(self):
        choices = self.choices.items()
        self.fields['choice'] = forms.MultipleChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.CheckboxSelectMultiple,
        )


class DateRangeForm(AbstractNodeForm):

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop('initial', {})
        choice = initial.pop('choice', {})
        if choice:
            start = choice.pop('start')
            end = choice.pop('end')
            question = {}
            question['lower'] = date(*map(int, start.split('-')))
            question['upper'] = date(*map(int, end.split('-')))
        initial['choice'] = choice
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def _add_choice_field(self):
        self.fields['choice'] = DateRangeField(
            label=self.label,
            help_text=self.help_text,
        )

    def serialize(self):
        if self.is_bound:
            data = self.cleaned_data['choice']
            assert data, "Dateranges may not be empty"
            start, end = data.lower, data.upper
            return {
                'choice':
                    {
                        'start': start.isoformat(),
                        'end': end.isoformat(),
                    },
                'notes': self.cleaned_data.get('notes', ''),
            }
        return {}

    def pprint(self):
        if self.is_valid():
            return '{}–{}'.format(self.serialize())
        return 'Not set'


class ReasonForm(AbstractNodeForm):

    def _add_choice_field(self):
        self.fields['choice'] = forms.CharField(
            label=self.label,
            help_text=self.help_text,
            widget=forms.Textarea,
        )


class PositiveIntegerForm(AbstractNodeForm):

    def _add_choice_field(self):
        self.fields['choice'] = forms.IntegerField(
            min_value=1,
            label=self.label,
            help_text=self.help_text,
        )


def make_form(question, **kwargs):
    kwargs.pop('prefix', None)
    kwargs.pop('instance', None)
    choices = kwargs.get('choices', None)
    answerdict = {
        'question': question,
        'prefix': str(question.pk),
        'label': question.label,
    }
    kwargs.update(answerdict)
    if question.input_type == 'bool':
        form_type = BooleanForm
    elif question.input_type == 'choice' and choices:
        form_type = ChoiceForm
        kwargs['choices'] = choices
    elif question.input_type == 'multichoiceonetext' and choices:
        form_type = MultipleChoiceOneTextForm
        kwargs['choices'] = choices
    elif question.input_type == 'daterange':
        form_type = DateRangeForm
    elif question.input_type == 'reason':
        form_type = ReasonForm
    elif question.input_type == 'positiveinteger':
        form_type = PositiveIntegerForm
    else:
        assert False, 'Unknown input type: {}'.format(question.input_type)
    return form_type(**kwargs)
