from django.contrib import messages
from django.urls import reverse
from django.views.generic import FormView, RedirectView

from .forms import FullnameForm


class GetFullnameView(FormView):
    login_required = False
    form_class = FullnameForm
    template_name = 'easydmp/auth/get_fullname_form.html'

    def post(self, request, *args, **kwargs):
        # Noop, page visited directly and not during login
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        backend = self.kwargs['backend']
        token = self.request.GET.get('partial_token')
        context['backend'] = backend
        context['token'] = token
        nexthop = 'social:complete'  # We're logging in!
        if not token:  # Direct access
            nexthop = 'missing-info'
            messages.info(self.request, 'The submit button only works while logging in')
        context['nexthop'] = reverse(nexthop, kwargs={'backend': backend})
        return context
