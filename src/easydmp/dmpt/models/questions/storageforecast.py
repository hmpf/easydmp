from django.core.exceptions import ValidationError
from django import forms
from django.utils.safestring import mark_safe
from django.utils.timezone import now as tznow

from easydmp.dmpt.forms import AbstractNodeFormSet
from easydmp.dmpt.models.questions.mixins import SaveMixin, NoCheckMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.utils import get_question_type_from_filename, render_from_string


__all__ = [
    'StorageForecastQuestion',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'StorageForecastQuestion'


class StorageForecastWidget(forms.MultiWidget):
    BACKUP_ESTIMATE_CHOICES = [
         ('= 0%', '0%'),
         ('≤ 25%', 'Up to 25%'),
         ('≤ 50%', 'Up to 50%'),
         ('≤ 75%', 'Up to 75%'),
         ('≤ 100%', 'Up to 100%'),
    ]
    template_name = 'widgets/storageestimate_widget.html'

    def __init__(self, attrs=None, year=None, *args, **kwargs):
        if attrs is None:
            attrs = {}
        attrs.pop('placeholder', None)
        attrs.pop('year', None)
        self.year = year
        year_attrs = dict(placeholder="year", year=year)
        storage_estimate_attrs = dict(placeholder='storage estimate', min=0)
        backup_percentage_attrs = dict(placeholder='backup percentage')
        widgets = (
            forms.TextInput(attrs=year_attrs),
            forms.NumberInput(attrs=storage_estimate_attrs),
            forms.Select(attrs=backup_percentage_attrs, choices=self.BACKUP_ESTIMATE_CHOICES),
        )
        self.widgets = widgets
        super().__init__(widgets, {})

    def decompress(self, value):
        if value:
            return value['year'], value['storage_estimate'], value['backup_percentage']
        return (None, None, None)


class StorageForecastField(forms.MultiValueField):
    error_messages = {
        'required': "All fields are required.",
        'incomplete': "All fields must be filled out",
        'year_missing': '''"Year" has not been filled out''',
        'storage_estimate_missing': '''"Storage Estimate" has not been filled out''',
        'storage_estimate_negative': '''"Storage Estimate" cannot be less than 0''',
        'backup_percentage_missing': '''"Backup Percentage" has not been filled out''',
    }

    def __init__(self, *args, **kwargs):
        require_all_fields = kwargs.pop('require_all_fields', True)
        kwargs['widget'] = StorageForecastWidget
        fields = [
            forms.CharField(min_length=4, max_length=4, disabled=True, required=True),
            forms.IntegerField(label='', required=True),
            forms.ChoiceField(
                label='',
                choices=StorageForecastWidget.BACKUP_ESTIMATE_CHOICES,
                required=True,
            )
        ]
        super().__init__(fields=fields, error_messages=self.error_messages,
                         require_all_fields=require_all_fields, *args,
                         **kwargs)

    def compress(self, value):
        errors = []
        if not value[0]:
            errors.append(ValidationError(self.error_messages['year_missing'], code='year_missing'))
        if not str(value[1]):
            errors.append(ValidationError(self.error_messages['storage_estimate_missing'], code='storage_estimate_missing'))
        elif value[1] < 0:
            errors.append(ValidationError(self.error_messages['storage_estimate_negative'], code='storage_estimate_negative'))
        if not value[2]:
            errors.append(ValidationError(self.error_messages['backup_percentage_missing'], code='backup_percentage_missing'))
        if errors:
            raise ValidationError(errors)

        return {
            'year': value[0],
            'storage_estimate': value[1],
            'backup_percentage': value[2],
        }


class StorageForecastQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = 'storageforecast'
    DEFAULT_FRAMING_TEXT = """<p>Storage forecast:</p>
<ul class="storage-estimate">{% for obj in choices %}
    <li>{{ obj.year }}: {{ obj.storage_estimate }} TiB, backup {{ obj.backup_percentage }}</li>
{% endfor %}</ul>
"""

    class Meta:
        proxy = True

    def get_canned_answer(self, choice, **kwargs):
        if not choice:
            return self.get_optional_canned_answer()

        framing_text = self.framing_text if self.framing_text else self.DEFAULT_FRAMING_TEXT
        return mark_safe(render_from_string(framing_text, {'choices': choice}))

    def pprint(self, value):
        return value['text']

    def pprint_html(self, value):
        choices = value['choice']
        return self.get_canned_answer(choices)

    def validate_choice(self, data):
        choices = data.get('choice', [])
        if self.optional and not choices:
            return True
        for choice in choices:
            year = choice.get('year', None)
            storage_estimate = choice.get('storage_estimate', None)
            backup_percentage = choice.get('backup_percentage', None)
            if year and storage_estimate and backup_percentage:
                return True
        return False


class StorageForecastFormSetForm(forms.Form):
    choice = StorageForecastField(label='')
    choice.widget.attrs.update({'class': 'question-storageforecast'})

    def __init__(self, year, *args, **kwargs):
        self.year = year
        super().__init__(*args, **kwargs)
        self.fields['choice'].widget.attrs.update({'year': year})


class AbstractStorageForecastFormSet(AbstractNodeFormSet):
    FORM = StorageForecastFormSetForm
    TYPE = TYPE
    MIN_NUM = 5
    MAX_NUM = 5
    required = ['year', 'storage_estimate', 'backup_percentage']
    can_add = False
    start_year = int(tznow().year)

    @classmethod
    def generate_choice(cls, choice):
        return {
            'year': choice['year'],
            'storage_estimate': choice['storage_estimate'],
            'backup_percentage': choice['backup_percentage'],
        }

    def serialize_subform(self):
        json_schema = {
            'properties': {
                'year': {
                    'type': 'string',
                },
                'storage_estimate': {
                    'type': 'string',
                },
                'backup_percentage': {
                    'type': 'string',
                },
            },
        }
        return self._set_required_on_serialized_subform(json_schema)

    def get_form_kwargs(self, form_index):
        form_kwargs = super().get_form_kwargs(form_index)
        index = 0
        if form_index is not None:
            index = form_index
        form_kwargs['year'] = str(self.start_year + index)
        return form_kwargs
