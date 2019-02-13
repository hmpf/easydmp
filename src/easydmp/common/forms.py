from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


FORM_CLASS = 'blueForms'


class DeleteForm(forms.Form):

    def __init__(self, *args, **kwargs):
        kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-delete'
        self.helper.form_class = FORM_CLASS
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Yes'))
        self.helper.add_input(Submit('cancel', 'No'))
