from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .widgets import MultiEmailWidget


class MultiEmailField(forms.Field):
    message = 'Enter one or more valid email addresses, one per line.'
    code = 'invalid'
    widget = MultiEmailWidget

    def to_python(self, value):
        "Normalize data to a list of strings."
        # Return None if no input was given.
        if not value:
            return []
        return [v.strip() for v in value.split() if v != ""]

    def validate(self, value):
        "Check if value consists only of valid emails."

        # Use the parent's handling of required fields, etc.
        super().validate(value)
        try:
            for email in value:
                validate_email(email)
        except ValidationError:
            raise ValidationError(self.message, code=self.code)


class EmailAddressForm(forms.Form):
    email_addresses = MultiEmailField(
        help_text="Enter one or more email addresses, one per line"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_id = 'id-invite'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Invite'))
