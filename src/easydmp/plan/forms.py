from django.core.exceptions import ValidationError
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
        self.user = kwargs.pop('user', None)
        super(PlanForm, self).__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))

    def clean(self):
        super().clean()
        if self.user:
            template = self.cleaned_data['template_type']
            title = self.cleaned_data['title']
            groups = self.user.groups.all()
            qs_count = Plan.objects.filter(template=template, title=title,
                                           editor_group__in=groups).exists()
            if qs_count:
                error = 'You already have edit access to plans named {} for the template {}, please rename the plan'
                raise ValidationError(error.format(title, template))
