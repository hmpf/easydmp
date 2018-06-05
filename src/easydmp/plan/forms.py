from django.core.exceptions import ValidationError
from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from easydmp.dmpt.models import Template

from .models import Plan
from .models import PlanComment
from .models import PlanAccess


class CheckExistingTitleMixin:

    def get_existing_titles(self, template, user, version=None):
        qs = Plan.objects.filter(template=template)
        pas = PlanAccess.objects.filter(user=user)
        qs = qs.filter(accesses__in=pas)
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

    class Meta:
        model = Plan
        fields = ['title', 'abbreviation']

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        qs = Template.objects.exclude(published=None)
        if self.user and self.user.is_superuser:
            qs = Template.objects.all()
        self.qs = qs
        if self.qs.count() > 1:
            self.fields['template_type'] = forms.ModelChoiceField(queryset=qs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan-create'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Next'))

    def clean(self):
        super().clean()
        if self.qs.count() == 1:
            self.cleaned_data['template_type'] = self.qs.get()
        template = self.cleaned_data['template_type']
        if self.user:
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


class SaveAsPlanForm(CheckExistingTitleMixin, forms.ModelForm):
    CHOICES = ((True, 'Yes'), (False, 'No'))
    keep_users = forms.ChoiceField(
        choices=CHOICES,
        help_text='If "Yes", copy over all editors from the original plan',
        widget=forms.RadioSelect(choices=CHOICES),
    )

    class Meta:
        model = Plan
        fields = ['title', 'abbreviation']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan-save-as'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Save As'))

    def clean(self):
        super().clean()
        if self.user:
            title = self.cleaned_data['title']
            self.is_valid_title(title, self.user, self.instance.template)


class PlanCommentForm(forms.ModelForm):
    class Meta:
        model = PlanComment
        fields = ['comment']


class ConfirmForm(forms.Form):

    def __init__(self, *args, **kwargs):
        kwargs.pop('instance')
        super().__init__(*args, **kwargs)

        # crispy forms
        self.helper = FormHelper()
        self.helper.form_id = 'id-plan-publish'
        self.helper.form_class = 'blueForms'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Yes'))
        self.helper.add_input(Submit('cancel', 'No'))
