from psycopg2.extras import DateRange

from django import forms
from django.core import exceptions
from django.forms.widgets import MultiWidget
from django.utils.translation import ugettext_lazy as _

__all__ = [
    'DateRangeField',
    'NamedURLField',
    'ChoiceNotListedField',
    'MultipleChoiceNotListedField',
]


class DateRangeWidget(MultiWidget):
    template_name = 'widgets/daterange_widget.html'

    def __init__(self, attrs=None, date_format=None, *args, **kwargs):
        default_attrs = {'class': 'dateinput'}
        if attrs:
            attrs.update(**default_attrs)
        else:
            attrs = default_attrs
        widgets = (
            forms.DateInput(attrs=attrs, format=date_format),
            forms.DateInput(attrs=attrs, format=date_format),
        )
        self.widgets = widgets
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value and all(value):
            return (value['lower'], value['upper'])
        return (None, None)


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
            self.base_field(), self.base_field()
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
            raise exceptions.ValidationError(
                self.error_messages['bound_ordering'],
                code='bound_ordering',
            )
        try:
            range_value = self.range_type(lower, upper)
        except TypeError:
            raise exceptions.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )
        else:
            return range_value


class NamedURLWidget(forms.MultiWidget):
    template_name = 'widgets/namedurl_widget.html'

    def __init__(self, attrs=None, *args, **kwargs):
        widgets = (
            forms.URLInput(attrs=attrs),
            forms.TextInput(attrs=attrs),
        )
        self.widgets = widgets
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            url, name = value['url'], value['name']
            return url, name
        return (None, None)


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
            raise forms.ValidationError('URL not entered')
        return {'url': value[0], 'name': value[1]}


class SelectNotListed(MultiWidget):
    template_name = 'widgets/selectnotlisted_widget.html'
    is_required = False
    required = False

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        assert choices, 'No "choices" given'
        widgets = (
            forms.Select(attrs=attrs, choices=choices),
            forms.CheckboxInput(attrs=attrs),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is not None:
            choices = value.get('choices', None)
            listed = value.get('not-listed', None)
            return (choices, listed)
        return (None, None)


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
        super().__init__(fields=fields, error_messages=error_messages,
                         widget=widget, *args, **kwargs)

    def validate(self, value):
        values = (value.get('choices', False), value.get('not-listed', False))
        if not any(values):
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')

    def compress(self, value):
        if not any(value):
            raise forms.ValidationError('At least one of the fields must be filled out')
        return {'choices': value[0], 'not-listed': value[1]}


class SelectMultipleNotListed(MultiWidget):
    template_name = 'widgets/selectmultiplenotlisted_widget.html'
    is_required = False
    required = False

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        assert choices, 'No "choices" given'
        widgets = (
            forms.SelectMultiple(attrs=attrs, choices=choices),
            forms.CheckboxInput(attrs=attrs),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is not None:
            choices = value.get('choices', None)
            listed = value.get('not-listed', None)
            return (choices, listed)
        return (None, None)


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
        super().__init__(fields=fields, error_messages=error_messages,
                         widget=widget, *args, **kwargs)

    def validate(self, value):
        values = (value.get('choices', False), value.get('not-listed', False))
        if not any(values):
            raise ValidationError(self.error_messages['incomplete'], code='incomplete')

    def compress(self, value):
        if not any(value):
            raise forms.ValidationError('At least one of the fields must be filled out')
        return {'choices': value[0], 'not-listed': value[1]}
