from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from easydmp.lib.stats import stats


__all__ = [
    'Homepage',
    'LoginView',
    'logout_view',
]


class PublicTemplateView(TemplateView):
    login_required = False


class Homepage(TemplateView):
    template_name = 'index.html'
    login_required = False

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('plan_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = stats()
        return context


class LoginView(TemplateView):
    template_name = 'login.html'
    login_required = False

    def get_context_data(self, **kwargs):
        providers = getattr(settings, 'EASYDMP_SOCIAL_AUTH_LOGIN_MENU', [])
        context = super().get_context_data(**kwargs)
        context['providers'] = providers
        return context


def logout_view(request):
    logout(request)
    return redirect('home', permanent=False)
