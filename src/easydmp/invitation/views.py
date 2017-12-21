from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic.edit import FormMixin
from django.views.generic import FormView
from django.views.generic import DetailView
from django.views.generic import UpdateView
from django.views.generic import DeleteView
from django.views.generic.detail import SingleObjectMixin

from easydmp.plan.models import Plan

from .models import PlanEditorInvitation
from .forms import EmailAddressForm


class CreatePlanEditorInvitationView(LoginRequiredMixin, SingleObjectMixin, FormView):
    """Invite user via email address to edit specific plan"""
    template_name = 'easydmp/invitation/plan/invitation_form.html'
    model = Plan
    pk_url_kwarg = 'plan'
    form_class = EmailAddressForm

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        kwargs = {
            'plan': self.object.pk,
        }
        return reverse('invitation_plan_editor_list', kwargs=kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'].helper.form_action = reverse(
            'invitation_plan_editor_create',
            kwargs={'plan': self.object.pk}
        )
        return context

    def form_valid(self, form):
        invited_by = self.request.user
        plan = self.get_object()
        sent = 0
        for address in form.cleaned_data['email_addresses']:
            invitation = PlanEditorInvitation(plan=plan, invited_by=invited_by,
                                              email_address=address)
            invitation.save()
            sent += invitation.send_invitation(request=self.request)
        return HttpResponseRedirect(self.get_success_url())


class ResendPlanEditorInvitationView(LoginRequiredMixin, UpdateView):
    """Invite user via email address to edit specific plan"""
    model = PlanEditorInvitation
    fields = []
    template_name = 'easydmp/invitation/plan/resend_editor_form.html'
    pk_url_kwarg = 'uuid'

    def get_success_url(self):
        return reverse('invitation_plan_editor_list', kwargs={'plan': self.object.plan.pk})

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.send_invitation(request=self.request)
        return HttpResponseRedirect(self.get_success_url())


class AcceptPlanEditorInvitationView(LoginRequiredMixin, UpdateView):
    "Accept an invitation to edit a specific plan"
    model = PlanEditorInvitation
    fields = []
    pk_url_kwarg = 'uuid'
    template_name = 'easydmp/invitation/plan/accept_editor_form.html'

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.plan.pk})

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.accept_invitation(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class ListPlanEditorInvitationView(LoginRequiredMixin, DetailView):
    "List all invitations for a specific plan"
    model = Plan
    pk_url_kwarg = 'plan'
    template_name = 'easydmp/invitation/plan/invitation_list.html'

    def get_editor_invitations(self):
        return PlanEditorInvitation.objects.filter(plan=self.object)

    def get_context_data(self, **kwargs):
        data = {}
        data.update(**super().get_context_data(**kwargs))
        data['plan_editor_invitations'] = self.get_editor_invitations()
        return data


class RevokePlanEditorInvitationView(LoginRequiredMixin, DeleteView):
    "Delete a not-accepted invitation"
    model = PlanEditorInvitation
    pk_url_kwarg = 'uuid'
    template_name = 'easydmp/invitation/plan/invitation_confirm_delete.html'

    def get_success_url(self):
        return reverse('invitation_plan_editor_list', kwargs={'plan': self.object.plan.pk})

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.revoke_invitation()
        return HttpResponseRedirect(success_url)
