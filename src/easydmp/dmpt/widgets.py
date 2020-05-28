from django import forms
from django.forms.widgets import MultiWidget, DateInput

from django_select2.forms import Select2Widget
from django_select2.forms import Select2MultipleWidget

__all__ = [
    # select2
    'Select2Widget',
    'Select2MultipleWidget',

    # simple: overrides default widgets
    'DMPTDateInput',
    'DMPTRadioSelect',

    # complex: form in a field
    'DateRangeWidget',
    'NamedURLWidget',
    'SelectNotListed',
    'SelectMultipleNotListed',
    'DMPTypedReasonWidget',
    'RDACostWidget',
]


# Overridden standard widgets


class DMPTDateInput(DateInput):
    input_type = 'date'


class DMPTRadioSelect(forms.RadioSelect):
    template_name = 'widgets/radio.html'
    option_template_name = 'widgets/radio_option.html'


# Multiwidgets


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


class SelectNotListed(MultiWidget):
    template_name = 'widgets/selectnotlisted_widget.html'
    is_required = False
    required = False

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        assert choices, 'No "choices" given'
        widgets = (
            Select2Widget(attrs=attrs, choices=choices),
            forms.CheckboxInput(attrs=attrs),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is not None:
            choices = value.get('choices', None)
            listed = value.get('not-listed', None)
            return (choices, listed)
        return (None, None)


class SelectMultipleNotListed(MultiWidget):
    template_name = 'widgets/selectmultiplenotlisted_widget.html'
    is_required = False
    required = False

    def __init__(self, attrs=None, choices=(), *args, **kwargs):
        assert choices, 'No "choices" given'
        widgets = (
            Select2MultipleWidget(attrs=attrs, choices=choices),
            forms.CheckboxInput(attrs=attrs),
        )
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value is not None:
            choices = value.get('choices', None)
            listed = value.get('not-listed', None)
            return (choices, listed)
        return (None, None)


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
