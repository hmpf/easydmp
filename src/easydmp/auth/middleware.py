from django.conf import settings
from django.contrib import auth
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured
from django.utils.deprecation import MiddlewareMixin
from django.utils.encoding import force_text
from rest_framework import exceptions as drf_exceptions

from .authentication import TokenAuthentication


class LoginRequiredMiddleware(MiddlewareMixin):

    def __init__(self, get_response=None):
        self.public_urls = getattr(settings, 'PUBLIC_URLS', ())
        self.login_url = force_text(settings.LOGIN_URL)
        self.get_response = get_response

    def process_view(self, request, view_func, _view_args, _view_kwargs):
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The TokenAuthenticationMiddleware requires authentication middleware "
                "to be installed. Edit your MIDDLEWARE%s setting to insert "
                "'django.contrib.auth.middleware.AuthenticationMiddleware' "
                "before this middleware." % (
                    "_CLASSES" if settings.MIDDLEWARE is None else ""
                )
            )

        # If CBV has the attribute login_required == False, allow
        view_class = getattr(view_func, 'view_class', None)
        if view_class and not getattr(view_class, 'login_required', True):
            return None

        # If view_func.login_required == False, allow
        if not getattr(view_func, 'login_required', True):
            return None

        # If path is public, allow
        for url in self.public_urls:
            if request.path.startswith(url):
                return None

        # Allow authenticated users
        if request.user.is_authenticated:
            return None

        # Redirect unauthenticated users to login page
        return redirect_to_login(request.get_full_path(), self.login_url, 'next')


class TokenAuthenticationMiddleware(MiddlewareMixin):

    def process_request(self, request):
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The TokenAuthenticationMiddleware requires authentication middleware "
                "to be installed. Edit your MIDDLEWARE%s setting to insert "
                "'django.contrib.auth.middleware.AuthenticationMiddleware' "
                "before this middleware." % (
                    "_CLASSES" if settings.MIDDLEWARE is None else ""
                )
            )

        user = None
        try:
            result = TokenAuthentication().authenticate(request)
            if result is not None:
                user, _ = result
        except drf_exceptions.AuthenticationFailed:
            return

        if not user or not (user.is_active and user.is_superuser):
            return

        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.
        if request.user.is_authenticated:
            if request.user == user:
                return
            else:
                # An authenticated user is associated with the request, but
                # it does not match the authorized user in the header.
                auth.logout(request)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        username = user.username
        user = auth.authenticate(request, remote_user=username)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)
