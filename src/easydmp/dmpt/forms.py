from collections import OrderedDict
from copy import deepcopy
from datetime import date

from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from easydmp.eestore.models import EEStoreCache

from .models import Template
from .models import ExternalChoiceQuestion
from .fields import DateRangeField
from .fields import NamedURLField
from .fields import ChoiceNotListedField
from .fields import MultipleChoiceNotListedField
from .fields import DMPTypedReasonField
from .widgets import Select2Widget
from .widgets import Select2MultipleWidget


FORM_CLASS = 'blueForms'


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

    def __init__(self, **kwargs):
        kwargs = deepcopy(kwargs)  # Avoid changing the original kwargs
        self.has_prevquestion = kwargs.pop('has_prevquestion', False)
        self.question = kwargs.pop('question').get_instance()
        self.question_pk = self.question.pk
        label = self.question.label
        self.label = ' '.join((label, self.question.question))
        self.help_text = getattr(self.question, 'help_text', '')
        kwargs.pop('instance', None)
        initial = self.deserialize(kwargs.pop('initial', {}))
        kwargs.pop('prefix', None)
        prefix = 'q{}'.format(self.question_pk)
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
        raise NotImplemented


class AbstractNodeForm(AbstractNodeMixin, forms.Form):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._add_choice_field()

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
    json_type = 'boolean'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = forms.ChoiceField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            widget=forms.RadioSelect,
            required=not self.question.optional,
        )

    def pprint(self):
        if self.is_valid():
            return 'Yes' if self.cleaned_data['choice'] else 'No'
        return 'Not set'

    def serialize(self):
        out = {
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

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['type'] = 'boolean'
        return attrs


class ChoiceForm(AbstractNodeForm):
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


class MultipleChoiceOneTextForm(AbstractNodeForm):
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

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['items'] = {'type': 'string'}
        return attrs


class DateRangeForm(AbstractNodeForm):
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

    def serialize(self):
        if self.is_bound:
            data = self.cleaned_data['choice']
            if data and data.lower and data.upper:
                start, end = data.lower, data.upper
                return {
                    'choice':
                        {
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
        if self.is_valid() and not self.question.optional:
            return '{}–{}'.format(self.serialize())
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
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.CharField(
            label=self.label,
            help_text=self.help_text,
            widget=forms.Textarea,
            required=not self.question.optional,
        )


class SingleReasonForm(AbstractNodeForm):
    json_type = 'string'

    def _add_choice_field(self):
        self.fields['choice'] = forms.CharField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )


class PositiveIntegerForm(AbstractNodeForm):
    json_type = 'number'

    def _add_choice_field(self):
        self.fields['choice'] = forms.IntegerField(
            min_value=1,
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['exclusiveMinimum'] = 1
        return attrs


class ExternalChoiceForm(AbstractNodeForm):
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


class ExternalChoiceNotListedForm(AbstractNodeForm):
    json_type = 'object'

    def _add_choice_field(self):
        choices = self.question.get_choices()
        self.fields['choice'] = ChoiceNotListedField(
            label=self.label,
            help_text=self.help_text,
            choices=choices,
            required=not self.question.optional,
        )

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

    def serialize_choice(self):
        attrs = super().serialize_choice()
        attrs['items'] = {'type': 'string'}
        return attrs


class ExternalMultipleChoiceNotListedOneTextForm(AbstractNodeForm):
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
    json_type = 'object'

    def _add_choice_field(self):
        self.fields['choice'] = NamedURLField(
            label=self.label,
            help_text=self.help_text,
            required=not self.question.optional,
        )

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
    json_type = 'array'

    def deserialize(self, initial):
        data = initial.get('choice', [])
        for i, item in enumerate(data):
            data[i] = {'choice': item}
        return data

    @classmethod
    def generate_choice(cls, choice):
        raise NotImplemented

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

    def serialize_subform(self):
        raise NotImplemented


class NamedURLFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    choice = NamedURLField(label='') # Hide the label from crispy forms


class AbstractMultiNamedURLOneTextFormSet(AbstractNodeFormSet):

    @classmethod
    def generate_choice(cls, choice):
        return {'url': choice['url'], 'name': choice['name']}

    def serialize_subform(self):
        return {
            'properties': {
                'url': {
                    'type': 'string',
                    'format': 'uri',
                },
                'name': {
                    'type': 'string',
                },
            },
            'required': ['url'],
        }


MultiNamedURLOneTextFormSet = forms.formset_factory(
    NamedURLFormSetForm,
    min_num=1,
    formset=AbstractMultiNamedURLOneTextFormSet,
    can_delete=True,
)


class DMPTypedReasonFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    choice = DMPTypedReasonField(label='')


class AbstractMultiDMPTypedReasonOneTextFormSet(AbstractNodeFormSet):

    @classmethod
    def generate_choice(cls, choice):
        return {
            'reason': choice['reason'],
            'type': choice['type'],
            'access_url': choice.get('access_url', ''),
        }

    def serialize_subform(self):
        return {
            'properties': {
                'type': {
                    'type': 'string',
                },
                'access_url': {
                    'type': 'string',
                    'format': 'uri',
                },
                'reason': {
                    'type': 'string',
                },
            },
            'required': ['type'],
        }


MultiDMPTypedReasonOneTextFormSet = forms.formset_factory(
    DMPTypedReasonFormSetForm,
    min_num=1,
    formset=AbstractMultiDMPTypedReasonOneTextFormSet,
    can_delete=True,
)


INPUT_TYPE_TO_FORMS = {
    'bool': BooleanForm,
    'choice': ChoiceForm,
    'multichoiceonetext': MultipleChoiceOneTextForm,
    'daterange': DateRangeForm,
    'reason': ReasonForm,
    'singlereason' : SingleReasonForm,
    'positiveinteger': PositiveIntegerForm,
    'externalchoice': ExternalChoiceForm,
    'extchoicenotlisted': ExternalChoiceNotListedForm,
    'externalmultichoiceonetext': ExternalMultipleChoiceOneTextForm,
    'extmultichoicenotlistedonetext': ExternalMultipleChoiceNotListedOneTextForm,
    'namedurl': NamedURLForm,
    'multinamedurlonetext': MultiNamedURLOneTextFormSet,
    'multidmptypedreasononetext': MultiDMPTypedReasonOneTextFormSet,
}


def make_form(question, **kwargs):
    kwargs.pop('prefix', None)
    kwargs.pop('instance', None)
    kwargs['question'] = question
    form_type = INPUT_TYPE_TO_FORMS.get(question.input_type, None)
    if form_type is None:
        assert False, 'Unknown input type: {}'.format(question.input_type)
    form = form_type(**kwargs)
    if not question.optional and isinstance(form, forms.BaseFormSet):
        form.validate_min = True
    return form_type(**kwargs)
