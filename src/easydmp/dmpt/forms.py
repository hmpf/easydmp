from datetime import date

from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from easydmp.eestore.models import EEStoreCache

from .models import Template
from .models import ExternalChoiceQuestion
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
        self.question = kwargs.pop('question')
        self.question_pk = self.question.pk
        self.label = kwargs.pop('label')
        self.help_text = getattr(self.question.pk, 'help_text', '')
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
        choices = self.question.canned_answers.values_list('choice', 'canned_text')
        fixed_choices = []
        for (k, v) in choices:
            if not v:
                v = k
            fixed_choices.append((k, v))
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=fixed_choices,
            widget=forms.RadioSelect,
        )


class MultipleChoiceOneTextForm(AbstractNodeForm):

    def _add_choice_field(self):
        choices = self.question.canned_answers.values_list('choice', 'choice')
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


class ExternalChoiceForm(AbstractNodeForm):

    def _add_choice_field(self):
        question = self.question.get_instance()
        if question.eestore.sources.exists():
            sources = question.eestore.sources.all()
        else:
            sources = question.eestore.eestore_type.sources.all()
        qs = EEStoreCache.objects.filter(source__in=sources)
        choices = qs.values_list('eestore_pid', 'name')
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            # widget: select 2?
        )


class ExternalMultipleChoiceOneTextForm(AbstractNodeForm):

    def _add_choice_field(self):
        question = self.question.get_instance()
        if question.eestore.sources.exists():
            sources = question.eestore.sources.all()
        else:
            sources = question.eestore.eestore_type.sources.all()
        qs = EEStoreCache.objects.filter(source__in=sources)
        choices = qs.values_list('eestore_pid', 'name')
        self.fields['choice'] = forms.MultipleChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            # widgrt: select2?
        )


INPUT_TYPE_TO_FORMS = {
    'bool': BooleanForm,
    'choice': ChoiceForm,
    'multichoiceonetext': MultipleChoiceOneTextForm,
    'daterange': DateRangeForm,
    'reason': ReasonForm,
    'positiveinteger': PositiveIntegerForm,
    'externalchoice': ExternalChoiceForm,
    'externalmultichoiceonetext': ExternalMultipleChoiceOneTextForm,
}


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
    form_type = INPUT_TYPE_TO_FORMS.get(question.input_type, None)
    if form_type is None:
        assert False, 'Unknown input type: {}'.format(question.input_type)
    return form_type(**kwargs)
