from collections import OrderedDict

from psycopg2.extras import DateRange

from django import forms
from django.core.exceptions import ValidationError
from django.forms.widgets import MultiWidget
from django.utils.translation import gettext_lazy as _

from .widgets import *

__all__ = [
    'DateRangeField',
    'NamedURLField',
    'ChoiceNotListedField',
    'MultipleChoiceNotListedField',
    'DMPTypedReasonField',
]


class DateRangeField(forms.MultiValueField):
    widget = DateRangeWidget
    default_error_messages = {'invalid': _('Enter two valid dates.')}
    base_field = forms.DateField
    range_type = DateRange
    default_error_messages = {
        'invalid': _('Enter two valid values.'),
        'bound_ordering': _('The start of the range must not exceed the end of the range.'),
    }
    required = True
    require_all_fields = True

    def __init__(self, *args, **kwargs):
        fields = [
            self.base_field(required=True),
            self.base_field(required=True),
        ]
        super().__init__(fields, *args, **kwargs)

    def prepare_value(self, value):
        lower_base, upper_base = self.fields
        if isinstance(value, self.range_type):
            return [
                lower_base.prepare_value(value.lower),
                upper_base.prepare_value(value.upper),
            ]
        if not value:
            return [
                lower_base.prepare_value(None),
                upper_base.prepare_value(None),
            ]
        return value

    def compress(self, values):
        if not values:
            return None
        lower, upper = values
        if lower is not None and upper is not None and lower > upper:
            raise ValidationError(
                self.error_messages['bound_ordering'],
                code='bound_ordering',
            )
        try:
            range_value = self.range_type(lower, upper)
        except TypeError:
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )
        else:
            return range_value

    def serialize(self):
        fixed_attrs = (
            ('title', str(self.__name__)),
            ('widget', str(self.widget)),

        )
        field_dict = OrdereDict(fixed_attrs)
        return field_dict


class NamedURLField(forms.MultiValueField):

    def __init__(self, *args, **kwargs):
        kwargs['widget'] = NamedURLWidget
        kwargs['require_all_fields'] = False
        fields = [
            forms.URLField(
                required=True,
                error_messages={
                    'incomplete': 'Enter at least a URL',
                }
            ),
            forms.CharField(required=False),
        ]
        super().__init__(fields, *args, **kwargs)

    def compress(self, value):
        if self.required and not value[0]:
            raise ValidationError('URL not entered')
        return {'url': value[0], 'name': value[1]}


class ChoiceNotListedField(forms.MultiValueField):

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        error_messages = {
            'incomplete': 'At least one of the fields must be filled out',
        }
        kwargs['require_all_fields'] = True
        kwargs['required'] = False
        widget = SelectNotListed(attrs=attrs, choices=choices)
        fields = [
            forms.ChoiceField(required=False, choices=choices),
            forms.BooleanField(required=False),
        ]
        self.choices = choices
        super().__init__(fields=fields, error_messages=error_messages,
                         widget=widget, *args, **kwargs)

    def validate(self, value):
        values = (value.get('choices', False), value.get('not-listed', False))
        if not any(values):
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')

    def compress(self, value):
        if not any(value):
            raise ValidationError('At least one of the fields must be filled out')
        return {'choices': value[0], 'not-listed': value[1]}


class MultipleChoiceNotListedField(forms.MultiValueField):

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        error_messages = {
            'incomplete': 'At least one of the fields must be filled out',
        }
        kwargs['require_all_fields'] = True
        kwargs['required'] = False
        widget = SelectMultipleNotListed(attrs=attrs, choices=choices)
        fields = [
            forms.MultipleChoiceField(required=False, choices=choices),
            forms.BooleanField(required=False),
        ]
        self.choices = choices
        super().__init__(fields=fields, error_messages=error_messages,
                         widget=widget, *args, **kwargs)

    def validate(self, value):
        values = (value.get('choices', False), value.get('not-listed', False))
        if not any(values):
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')

    def compress(self, value):
        if not any(value):
            raise ValidationError('At least one of the fields must be filled out')
        return {'choices': value[0], 'not-listed': value[1]}


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
            #    error_messages={'incomplete': 'Enter a valid currency code.'},
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
            'value': value[3]
        }
