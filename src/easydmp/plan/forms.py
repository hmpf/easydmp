from django.core.exceptions import ValidationError
from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from easydmp.dmpt.models import Template

from .models import Plan


class CheckExistingTitleMixin:

    def get_existing_titles(self, template, user, version=None):
        groups = user.groups.all()
        qs = Plan.objects.filter(template=template, editor_group__in=groups)
        if version is not None:
            qs = qs.filter(version=version)
        return qs

    def is_valid_title(self, title, user, template):
        version = None
        if self.instance:
            version = self.instance.version
        qs = self.get_existing_titles(template, self.user, version)
        qs_count = qs.filter(title=title)
        if qs_count:
            error = 'You already have edit access to plans named {} for the template {}, please rename the plan'
            raise ValidationError(error.format(title, template))


class NewPlanForm(CheckExistingTitleMixin, forms.ModelForm):
    template_type = forms.ModelChoiceField(queryset=Template.objects.exclude(published=None))

    class Meta:
        model = Plan
        fields = ['title', 'abbreviation']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan-create'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))

    def clean(self):
        super().clean()
        if self.user:
            template = self.cleaned_data['template_type']
            title = self.cleaned_data['title']
            self.is_valid_title(title, self.user, template)


class UpdatePlanForm(CheckExistingTitleMixin, forms.ModelForm):

    class Meta:
        model = Plan
        fields = ['title', 'abbreviation']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan-update'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Rename'))

    def clean(self):
        super().clean()
        if self.user:
            title = self.cleaned_data['title']
            self.is_valid_title(title, self.user, self.instance.template)
