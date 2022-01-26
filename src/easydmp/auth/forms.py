from django import forms


class FullnameForm(forms.Form):
    fullname = forms.CharField(max_length=200)


class EmailForm(forms.Form):
    email = forms.EmailField()
