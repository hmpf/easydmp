from django.core.exceptions import ValidationError
from django import forms
from django.utils.safestring import mark_safe
from django.utils.timezone import now as tznow

from easydmp.dmpt.forms import AbstractNodeFormSet
from easydmp.dmpt.models.questions.mixins import SaveMixin, NoCheckMixin
from easydmp.dmpt.models.base import Question
from easydmp.dmpt.utils import get_question_type_from_filename, render_from_string


__all__ = [
    'MultiDMPTypedReasonOneTextQuestion',
]

TYPE = get_question_type_from_filename(__file__)
QUESTION_CLASS = 'MultiDMPTypedReasonOneTextQuestion'


class DMPTypedReasonWidget(forms.MultiWidget):
    template_name = 'widgets/dmptypedreason_widget.html'

    def __init__(self, attrs=None, *args, **kwargs):
        reason_attrs = {} if attrs is None else attrs.copy()
        reason_attrs['placeholder'] = 'reason'
        widgets = (
            forms.TextInput(attrs=attrs),
            forms.Textarea(attrs=reason_attrs),
            forms.URLInput(attrs=attrs),
        )
        self.widgets = widgets
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value['type'], value['reason'], value['access_url']
        return (None, None, None)


class DMPTypedReasonField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = DMPTypedReasonWidget
        kwargs['require_all_fields'] = True
        kwargs['required'] = False
        fields = [
            forms.CharField(
                required=True, error_messages={'incomplete': 'Enter a data type.'},
            ),
            forms.CharField(
                required=True, error_messages={'incomplete': 'Enter a reason.'},
            ),
            forms.URLField(required=False),
        ]
        super().__init__(fields, *args, **kwargs)

    def compress(self, value):
        if not value:
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')
        return {'type': value[0], 'reason': value[1], 'url': value[2]}


class MultiDMPTypedReasonOneTextQuestion(NoCheckMixin, SaveMixin, Question):
    """A non-branch-capable question answerable several type+reason+url sets

    The url is optional.

    The framing text for the canned answer utilizes the Django template system,
    not standard python string formatting. If there is no framing text
    a serialized version of the raw choice is returned.
    """

    TYPE = 'multidmptypedreasononetext'
    DEFAULT_FRAMING_TEXT = """<dl>{% for triple in choices %}
<dt>{{ triple.type }}</dt>
<dd>Because {{ triple.reason }}</dd>
{% if triple.access_url %}<dd><a href="{{ triple.access_url }}">Access instructions</a></dd>{% endif %}
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
            type_ = choice.get('type', None)
            reason = choice.get('reason', None)
            if type_ and reason:
                return True
        return False


class DMPTypedReasonFormSetForm(forms.Form):
    # Low magic form to be used in a formset
    #
    # The formset has the node-magic
    choice = DMPTypedReasonField(label='')
    choice.widget.attrs.update({'class': 'question-multidmptypedreasononetext'})


class AbstractMultiDMPTypedReasonOneTextFormSet(AbstractNodeFormSet):
    FORM = DMPTypedReasonFormSetForm
    TYPE = 'multidmptypedreasononetext'
    required = ['type']

    @classmethod
    def generate_choice(cls, choice):
        return {
            'reason': choice['reason'],
            'type': choice['type'],
            'access_url': choice.get('access_url', ''),
        }

    def serialize_subform(self):
        json_schema = {
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
        }
        return self._set_required_on_serialized_subform(json_schema)
