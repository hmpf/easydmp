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


def user_details(strategy, details, backend, user=None, *args, **kwargs):
    """Update user details using data from provider

    Replaces social.pipeline.user.user_details
    """

    if not user:
        return

    changed = False  # flag to track changes
    protected = ('username', 'id', 'pk', 'email') + \
                tuple(strategy.setting('PROTECTED_USER_FIELDS', []))

    # Update user model attributes with the new data sent by the current
    # provider. Update on some attributes is disabled by default, for
    # example username and id fields. It's also possible to disable update
    # on fields defined in SOCIAL_AUTH_PROTECTED_USER_FIELDS.
    field_mapping = strategy.setting('USER_FIELD_MAPPING', {}, backend)
    for name, value in details.items():
        # Convert to existing user field if mapping exists
        name = field_mapping.get(name, name)
        if value is None or not hasattr(user, name) or name in protected:
            continue

        # Check https://github.com/omab/python-social-auth/issues/671
        current_value = getattr(user, name, None)
        if current_value or current_value == value:
            continue

        changed = True
        setattr(user, name, value)

    if changed:
        strategy.storage.user.changed(user)
