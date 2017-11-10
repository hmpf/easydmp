from psycopg2.extras import DateRange, DateTimeTZRange, NumericRange

from django import forms
from django.core import exceptions
from django.forms.widgets import MultiWidget
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

__all__ = ['DateRangeField']


class DateRangeWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = (forms.DateInput, forms.DateInput)
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return (value['lower'], value['upper'])
        return (None, None)

    def format_output(self, rendered_widgets):
        widget_context = {'lower': rendered_widgets[0], 'upper': rendered_widgets[1],}
        return render_to_string('widgets/daterange_widget.html', widget_context)


class DateRangeField(forms.MultiValueField):
    default_error_messages = {'invalid': _('Enter two valid dates.')}
    base_field = forms.DateField
    range_type = DateRange
    default_error_messages = {
        'invalid': _('Enter two valid values.'),
        'bound_ordering': _('The start of the range must not exceed the end of the range.'),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('widget', DateRangeWidget())
        kwargs.setdefault('fields', [self.base_field(required=True), self.base_field(required=True)])
        kwargs.setdefault('required', True)
        kwargs.setdefault('require_all_fields', True)
        super().__init__(**kwargs)

    def prepare_value(self, value):
        lower_base, upper_base = self.fields
        if isinstance(value, self.range_type):
            return [
                lower_base.prepare_value(value.lower),
                upper_base.prepare_value(value.upper),
            ]
        if value is None:
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
