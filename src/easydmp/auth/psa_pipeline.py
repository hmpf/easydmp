from django.shortcuts import reverse
from django.utils.http import urlencode

from social_core.pipeline.partial import partial

from .forms import FullnameForm, EmailForm


@partial
def get_missing_full_name(strategy, details, current_partial, user=None, is_new=False, *args, **kwargs):
    if (user and user.get_full_name()) or details.get('fullname', None):
        # Fullname will be set in "user_details" if missing
        return

    fullname = strategy.request_data().get('fullname')
    form = FullnameForm({'fullname': fullname})  # Validate
    if form.is_valid():
        details['fullname'] = form.cleaned_data['fullname']
    else:
        backend_name = current_partial.backend
        token = current_partial.token
        base_url = reverse('missing-info', kwargs={'backend': backend_name})
        params = urlencode({'partial_token': token})
        url = '{}?{}'.format(base_url, params)
        return strategy.redirect(url)



@partial
def get_missing_email(strategy, details, current_partial, user=None, is_new=False, *args, **kwargs):
    if getattr(user, 'email', None) or details.get('email', None):
        # Email is already set and can be used by "get_username")
        return

    email = strategy.request_data().get('email')
    form = EmailForm({'email': email})  # Validate
    if form.is_valid():
        details['email'] = form.cleaned_data['email']
    else:
        backend_name = current_partial.backend
        token = current_partial.token
        base_url = reverse('missing-email', kwargs={'backend': backend_name})
        params = urlencode({'partial_token': token})
        url = '{}?{}'.format(base_url, params)
        return strategy.redirect(url)


def fix_orcid_username(backend, details, *args, **kwargs):
    if backend.name in ('orcid', 'orcid-sandbox'):
        orcid = details.pop('username')
