from collections import OrderedDict
from copy import deepcopy
from datetime import date, datetime

from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.forms import BaseFormSet

from easydmp.lib.forms import FORM_CLASS
from easydmp.eestore.models import EEStoreCache

from .models import Template
from .models import ExternalChoiceQuestion
from .models import Question
from .fields import DateRangeField
from .fields import NamedURLField
from .fields import ChoiceNotListedField
from .fields import MultipleChoiceNotListedField
from .utils import make_qid
from .widgets import DMPTDateInput
from .widgets import Select2Widget
from .widgets import Select2MultipleWidget


class TemplateForm(forms.ModelForm):
    template_type = forms.ModelChoiceField(
        queryset=Template.objects.filter(retired=None).exclude(published=None)
    )

    class Meta:
        model = Template
        fields = ['title']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan'
        self.helper.form_class = FORM_CLASS
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))


class NotesForm(forms.Form):
    notes = forms.CharField(
        label='More information',
        help_text='If you need to go more in depth, do so here. This will be shown in the generated text',
        required=False,
        widget=forms.Textarea
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)


class AbstractNodeMixin():
    json_type: str  # For JSON Schema, the "type"-keyword

    def __init__(self, **kwargs):
        kwargs = deepcopy(kwargs)  # Avoid changing the original kwargs
        self.has_prevquestion = kwargs.pop('has_prevquestion', False)
        self.question = kwargs.pop('question').get_instance()
        self.question_pk = self.question.pk
        self.input_class = 'question-{}'.format(self.question.input_type)
        label = self.question.label
        self.label = ' '.join((label, self.question.question))
        self.help_text = getattr(self.question, 'help_text', '')
        kwargs.pop('instance', None)
        initial = self.deserialize(kwargs.pop('initial', {}))
        kwargs.pop('prefix', None)
        prefix = make_qid(self.question_pk)
        super().__init__(initial=initial, prefix=prefix, **kwargs)

    def serialize_form(self):
        dict_form = OrderedDict(question_pk=self.question_pk)
        choice_attrs = OrderedDict(
            label=self.label,
            help_text=self.help_text,
            required=True,
            input=self.serialize_choice(),
        )
        notes = NotesForm.base_fields['notes']
        notes_attrs = OrderedDict(
            label=notes.label,
            help_text=notes.help_text,
            required=False,
            input={'type': 'string'}
        )
        dict_form['choice'] = choice_attrs
        dict_form['notes'] = notes_attrs
        return dict_form

    def serialize_choice(self):
        """For JSON Schema serialization

        All other keywords and structures needed for a type in addition to "type"
        """
        raise NotImplementedError


class AbstractNodeForm(AbstractNodeMixin, forms.Form):
    TYPE: str  # For registering the form with Question

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._add_choice_field()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Question.register_form_class(cls.TYPE, cls)

    def _add_choice_field(self):
        pass

    def deserialize(self, initial):
        return initial

    def serialize(self):
        return {
            'choice': self.cleaned_data['choice'],
        }

    def pprint(self):
        if self.is_valid():
            return self.cleaned_data['choice']
        return 'Not set'

    def serialize_choice(self):
        attrs = {'type': self.json_type}
        choices = getattr(self.fields['choice'], 'choices', None)
        if choices:
            attrs['choices'] = choices
        return attrs


class BooleanForm(AbstractNodeForm):
    TYPE = 'bool'
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


class ChoiceForm(AbstractNodeForm):
    TYPE = 'choice'
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


class MultipleChoiceOneTextForm(AbstractNodeForm):
    TYPE = 'multichoiceonetext'
    json_type = 'array'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = forms.MultipleChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.CheckboxSelectMultiple,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['items'] = {'type': 'string'}
        return attrs


class DateRangeForm(AbstractNodeForm):
    TYPE = 'daterange'
    json_type = 'object'

    def deserialize(self, initial):
        choice = initial.get('choice', {})
        if choice:
            start = choice.pop('start')
            end = choice.pop('end')
            question = {}
            question['lower'] = date(*map(int, start.split('-')))
            question['upper'] = date(*map(int, end.split('-')))
            initial['choice'] = question
        return initial

    def _add_choice_field(self):
        self.fields['choice'] = DateRangeField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'type': 'date', 'class': self.input_class})

    def serialize(self):
        if self.is_bound:
            data = self.cleaned_data['choice']
            if data and data.lower and data.upper:
                start, end = data.lower, data.upper
                return {
                    'choice': {
                        'start': start.isoformat(),
                        'end': end.isoformat(),
                    },
                }
            else:
                if self.question.optional:
                    return {}
                else:
                    raise ValueError("Dateranges may not be empty")
        return {}

    def pprint(self):
        if self.is_valid():
            choice = self.serialize()['choice']
            try:
                return f"{choice['start']}–{choice['end']}"
            except KeyError:
                pass
        return 'Not set'

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['properties'] = {
            'start': {
                'description': 'Start date',
                'format': 'date',
                'type': 'string',
            },
            'end': {
                'description': 'End date',
                'format': 'date',
                'type': 'string',
            },
        }
        attrs['required'] = ['start', 'end']
        return attrs


class ReasonForm(AbstractNodeForm):
    TYPE = 'reason'
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.CharField(
            label=self.label,
            help_text=self.help_text,
            widget=forms.Textarea,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})


class ShortFreetextForm(AbstractNodeForm):
    TYPE = 'shortfreetext'
    json_type = 'string'
    MAX_LENGTH = 255

    def _add_choice_field(self):
        help_text = '(This field has a hard limit of {} letters.)'.format(
            self.MAX_LENGTH
        )
        if self.help_text:
            help_text = '{} {}'.format(self.help_text.strip(), help_text)
        self.fields['choice'] = forms.CharField(
            label=self.label,
            help_text=help_text,
            max_length=self.MAX_LENGTH,
            widget=forms.TextInput,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})


class PositiveIntegerForm(AbstractNodeForm):
    TYPE = 'positiveinteger'
    json_type = 'number'

    def _add_choice_field(self):
        self.fields['choice'] = forms.IntegerField(
            min_value=1,
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['exclusiveMinimum'] = 1
        return attrs


class DateForm(AbstractNodeForm):
    TYPE = 'date'
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.DateField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
            widget=DMPTDateInput,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})


class ExternalChoiceForm(AbstractNodeForm):
    TYPE = 'externalchoice'
    json_type = 'string'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=Select2Widget,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})


class ExternalChoiceNotListedForm(AbstractNodeForm):
    TYPE = 'extchoicenotlisted'
    json_type = 'object'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = ChoiceNotListedField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['properties'] = {
            'choices': {
                'type': 'string',
            },
            'not-listed': {'type': 'boolean'}
        }
        attrs['required'] = ['choices', 'not-listed']
        return attrs


class ExternalMultipleChoiceOneTextForm(AbstractNodeForm):
    TYPE = 'externalmultichoiceonetext'
    json_type = 'array'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = forms.MultipleChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=Select2MultipleWidget,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['items'] = {'type': 'string'}
        return attrs


class ExternalMultipleChoiceNotListedOneTextForm(AbstractNodeForm):
    TYPE = 'extmultichoicenotlistedonetext'
    json_type = 'object'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = MultipleChoiceNotListedField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            required=not self.question.optional,
        )

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['properties'] = {
            'choices': {
                'type': 'array',
                'items': {'string'},
            },
            'not-listed': {'type': 'boolean'}
        }
        attrs['required'] = ['choices', 'not-listed']
        return attrs


class NamedURLForm(AbstractNodeForm):
    # High magic form with node-magic that cannot be used in a formset
    TYPE = 'namedurl'
    json_type = 'object'

    def _add_choice_field(self):
        self.fields['choice'] = NamedURLField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )
        self.fields['choice'].widget.attrs.update({'class': self.input_class})

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['properties'] = {
            'url': {
                'type': 'string',
                'format': 'uri',
            },
            'name': {'type': 'string'}
        }
        attrs['required'] = ['url']
        return attrs


# Formsets


class AbstractNodeFormSet(AbstractNodeMixin, forms.BaseFormSet):
    can_add = True  # Whether adding extra rows is allowed
    json_type = 'array'
    MIN_NUM: int = 1  # Override in subclass
    MAX_NUM: int  # Override in subclass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Question.register_form_class(cls.TYPE, cls)

    def deserialize(self, initial):
        data = initial.get('choice', [])
        for i, item in enumerate(data):
            data[i] = {'choice': item}
        return data

    @classmethod
    def generate_choice(cls, choice):
        raise NotImplementedError

    def serialize(self):
        choices = []
        for form_choice in self.cleaned_data:
            if form_choice.get('DELETE', False): continue
            choice = form_choice.get('choice', None)
            if not choice: continue
            choice_dict = self.generate_choice(choice)
            choices.append(choice_dict)
        return {
            'choice': choices,
        }

    def serialize_choice(self):
        return OrderedDict(
            type=self.json_type,
            items=OrderedDict(
                type='object',
                **self.serialize_subform(),
            )
        )

    def _set_required_on_serialized_subform(self, serialized_subform):
        if not self.question.optional:
            serialized_subform['required'] = self.required
        return serialized_subform

    def serialize_subform(self):
        raise NotImplementedError

    @classmethod
    def generate_formset(cls, required=True):
        kwargs = {}
        if hasattr(cls, 'MAX_NUM'):
            kwargs['max_num'] = cls.MAX_NUM
            kwargs['validate_max'] = True
        cls.FORM.declared_fields['choice'].required = required
        return forms.formset_factory(
            cls.FORM,
            min_num=cls.MIN_NUM,
            formset=cls,
            can_delete=True,
            **kwargs,
        )


class NamedURLFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    choice = NamedURLField(label='') # Hide the label from crispy forms
    choice.widget.attrs.update({'class': 'question-multinamedurlonetext'})


class AbstractMultiNamedURLOneTextFormSet(AbstractNodeFormSet):
    FORM = NamedURLFormSetForm
    TYPE = 'multinamedurlonetext'
    required = ['url']

    @classmethod
    def generate_choice(cls, choice):
        return {'url': choice['url'], 'name': choice['name']}

    def serialize_subform(self):
        json_schema = {
            'properties': {
                'url': {
                    'type': 'string',
                    'format': 'uri',
                },
                'name': {
                    'type': 'string',
                },
            },
        }
        return self._set_required_on_serialized_subform(json_schema)


def make_form(question, **kwargs):
    kwargs.pop('prefix', None)
    kwargs.pop('instance', None)
    kwargs['question'] = question
    form_class = question.get_form_class()
    if issubclass(form_class, forms.BaseFormSet):
        form_class = form_class.generate_formset(required=not question.optional)
    form = form_class(**kwargs)
    if isinstance(form, forms.BaseFormSet):
        form.validate_min = not question.optional
    return form
