from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from easydmp.dmpt.models import Template

from .models import Plan


class PlanForm(forms.ModelForm):
    template_type = forms.ModelChoiceField(queryset=Template.objects.exclude(published=None))

    class Meta:
        model = Plan
        fields = ['title']

    def __init__(self, *args, **kwargs):
        super(PlanForm, self).__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))
