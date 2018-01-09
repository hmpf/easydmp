from django import forms
from django.forms.widgets import MultiWidget

__all__ = [
    # simple
    'DMPTRadioSelect',

    # complex
    'DateRangeWidget',
    'NamedURLWidget',
    'SelectNotListed',
    'SelectMultipleNotListed',
]


# Overridden standard widgets

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
