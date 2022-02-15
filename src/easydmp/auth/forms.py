from django import forms

from .models import User


class FullnameForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('full_name',)


class EmailForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('email',)
