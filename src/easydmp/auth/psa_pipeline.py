from django.shortcuts import reverse
from django.utils.http import urlencode

from social_core.pipeline.partial import partial

from .forms import FullnameForm


@partial
def get_missing_full_name(strategy, details, current_partial, user=None, is_new=False, *args, **kwargs):
    if (user and user.get_full_name()) or 'fullname' in details:
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
