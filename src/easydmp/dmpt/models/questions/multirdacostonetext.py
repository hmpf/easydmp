from django.core.exceptions import ValidationError
from django import forms
from django.utils.safestring import mark_safe

from easydmp.dmpt.forms import AbstractNodeFormSet
from easydmp.dmpt.models.questions.mixins import SaveMixin, NoCheckMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.utils import get_question_type_from_filename, render_from_string


__all__ = [
    'MultiRDACostOneTextQuestion',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'MultiRDACostOneTextQuestion'


class RDACostWidget(forms.MultiWidget):
    template_name = 'widgets/rdacost_widget.html'

    def __init__(self, attrs=None, *args, **kwargs):
        if attrs is None:
            attrs = {}
        attrs.pop('placeholder', None)
        currency_code_attrs = dict(placeholder='Currency code', **attrs)
        description_attrs = dict(placeholder='Description', **attrs)
        title_attrs = dict(placeholder='Title', **attrs)
        value_attrs = dict(placeholder='Value', **attrs)
        widgets = (
            forms.TextInput(attrs=currency_code_attrs),
            forms.Textarea(attrs=description_attrs),
            forms.TextInput(attrs=title_attrs),
            forms.NumberInput(attrs=value_attrs),
        )
        self.widgets = widgets
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value['currency_code'], value['description'], value['title'], value['value']
        return (None, None, None, None)


class RDACostField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):
        require_all_fields = kwargs.pop('require_all_fields', False)
        kwargs['widget'] = RDACostWidget
        error_messages = {'incomplete': 'Enter a title.'}
        fields = [
            forms.CharField(
                required=False,
                help_text="Currency code as per ISO 4217",
                # TODO: validate currency code
                # error_messages={'incomplete': 'Enter a valid currency code.'},
            ),
            forms.CharField(
                required=False,
            ),
            forms.CharField(
                label='Foo',
                required=True,
                error_messages={'incomplete': 'Enter a title.'},
            ),
            forms.IntegerField(required=False),
        ]
        super().__init__(fields=fields, error_messages=error_messages,
                         require_all_fields=require_all_fields, *args,
                         **kwargs)

    def compress(self, value):
        if not value and not value[2]:
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')
        return {
            'currency_code': value[0],
            'description': value[1],
            'title': value[2],
            'value': value[3],
        }


class MultiRDACostOneTextQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question for RDA DMP Common Standard Cost

    Only title is required.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = TYPE
    DEFAULT_FRAMING_TEXT = """<dl class="answer-cost">{% for obj in choices %}
<dt>{{ obj.title }}
{% if obj.currency_code or obj.value %}
<span>{{ obj.currency_code }} {{ obj.value|default_if_none:"Unknown" }}</span>
{% endif %}
</dt>
<dd>{{ obj.description|default:"-" }}</dd>
{% endfor %}
</dl>
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
            if choice.get('title', None):
                return True
        return False


class RDACostFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    choice = RDACostField(label='')
    choice.widget.attrs.update({'class': 'question-multirdacostonetext'})


class AbstractMultiRDACostOneTextFormSet(AbstractNodeFormSet):
    FORM = RDACostFormSetForm
    TYPE = TYPE
    required = ['title']

    @classmethod
    def generate_choice(cls, choice):
        return {
            'currency_code': choice['currency_code'],
            'description': choice['description'],
            'title': choice['title'],
            'value': choice['value'],
        }

    def serialize_subform(self):
        json_schema = {
            'properties': {
                'currency_code': {
                    'type': 'string',
                },
                'description': {
                    'type': 'string',
                },
                'title': {
                    'type': 'string',
                },
                'value': {
                    'type': 'number',
                },
            },
        }
        return self._set_required_on_serialized_subform(json_schema)
