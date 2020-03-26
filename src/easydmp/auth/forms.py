from django import forms


class FullnameForm(forms.Form):
    fullname = forms.CharField(max_length=200)
