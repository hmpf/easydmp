from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import FormView
from django.views.generic import DetailView
from django.views.generic import UpdateView
from django.views.generic import DeleteView
from django.views.generic.detail import SingleObjectMixin

from easydmp.plan.models import Plan

from .models import PlanEditorInvitation
from .models import PlanViewerInvitation
from .forms import EmailAddressForm


class AbstractCreatePlanInvitationView(SingleObjectMixin, FormView):
    model = Plan
    pk_url_kwarg = 'plan'
    form_class = EmailAddressForm

    def get_queryset(self):
        # Only editors may invite to a plan
        qs = super().get_queryset().editable(self.request.user)
        return qs

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
        return reverse(self.success_url_name, kwargs=self.get_url_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'].helper.form_action = reverse(
            self.self_url_name,
            kwargs=self.get_url_kwargs()
        )
        context['plan_invitations'] = self.get_invitations()
        return context

    def form_valid(self, form):
        invited_by = self.request.user
        plan = self.get_object()
        sent = 0
        for address in form.cleaned_data['email_addresses']:
            invitation = self.invitation_class(
                plan=plan,
                invited_by=invited_by,
                email_address=address,
            )
            invitation.save()
            sent += invitation.send_invitation(request=self.request)
        return HttpResponseRedirect(self.get_success_url())

    def get_url_kwargs(self):
        return {
            'plan': self.object.pk,
        }

    def get_invitations(self):
        manager = self.invitation_class.objects
        qs = manager.filter(type=self.invitation_class.invitation_type)
        return qs.filter(plan=self.object)


class CreatePlanEditorInvitationView(AbstractCreatePlanInvitationView):
    """Invite user via email address to edit specific plan"""
    template_name = 'easydmp/invitation/plan/edit/invitation_form.html'
    self_url_name = 'invitation_plan_editor_create'
    success_url_name = 'share_plan'
    invitation_class = PlanEditorInvitation


class CreatePlanViewerInvitationView(AbstractCreatePlanInvitationView):
    """Invite user via email address to view specific plan"""
    template_name = 'easydmp/invitation/plan/view/invitation_form.html'
    self_url_name = 'invitation_plan_viewer_create'
    success_url_name = 'share_plan'
    invitation_class = PlanViewerInvitation


class AbstractPlanInvitationView:
    fields = []
    pk_url_kwarg = 'uuid'

    def get_invitations(Self):
        return self.model.objects.filter(type=self.model.invitation_type)

    def get_success_url(self):
        return reverse(self.success_url_name, kwargs=self.get_url_kwargs())

    def get_url_kwargs(self):
        return {
            'plan': self.object.plan.pk,
        }


class AbstractResendPlanInvitationView(AbstractPlanInvitationView, UpdateView):

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.send_invitation(request=self.request)
        return HttpResponseRedirect(self.get_success_url())


class ResendPlanEditorInvitationView(AbstractResendPlanInvitationView):
    """Invite user via email address to edit specific plan"""
    model = PlanEditorInvitation
    template_name = 'easydmp/invitation/plan/edit/resend_form.html'
    success_url_name = 'share_plan'


class ResendPlanViewerInvitationView(AbstractResendPlanInvitationView):
    """Invite user via email address to view specific plan"""
    model = PlanViewerInvitation
    template_name = 'easydmp/invitation/plan/view/resend_form.html'
    success_url_name = 'share_plan'


class AbstractAcceptPlanInvitationView(AbstractPlanInvitationView, UpdateView):
    success_url_name = 'plan_detail'

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.accept_invitation(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class AcceptPlanEditorInvitationView(AbstractAcceptPlanInvitationView):
    "Accept an invitation to edit a specific plan"
    model = PlanEditorInvitation
    template_name = 'easydmp/invitation/plan/edit/accept_form.html'


class AcceptPlanViewerInvitationView(AbstractAcceptPlanInvitationView):
    "Accept an invitation to view a specific plan"
    model = PlanViewerInvitation
    template_name = 'easydmp/invitation/plan/view/accept_form.html'


class AbstractRevokePlanInvitationView(AbstractPlanInvitationView, DeleteView):

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.revoke_invitation()
        return HttpResponseRedirect(success_url)


class RevokePlanEditorInvitationView(AbstractRevokePlanInvitationView):
    "Delete a not-accepted invitation"
    model = PlanEditorInvitation
    template_name = 'easydmp/invitation/plan/edit/invitation_confirm_delete.html'
    success_url_name = 'share_plan'


class RevokePlanViewerInvitationView(AbstractRevokePlanInvitationView):
    "Delete a not-accepted invitation"
    model = PlanViewerInvitation
    template_name = 'easydmp/invitation/plan/view/invitation_confirm_delete.html'
    success_url_name = 'share_plan'


class AbstractListPlanInvitationView(DetailView):
    model = Plan
    pk_url_kwarg = 'plan'

    def get_invitations(self):
        qs = self.invitation_class.objects.filter(plan=self.object)
        return qs

    def get_context_data(self, **kwargs):
        data = {}
        data.update(**super().get_context_data(**kwargs))
        data['plan_invitations'] = self.get_invitations()
        return data


class ListPlanEditorInvitationView(AbstractListPlanInvitationView):
    "List all editor invitations for a specific plan"
    template_name = 'easydmp/invitation/plan/edit/invitation_list.html'
    invitation_class = PlanEditorInvitation


class ListPlanViewerInvitationView(AbstractListPlanInvitationView):
    "List all viewer invitations for a specific plan"
    template_name = 'easydmp/invitation/plan/view/invitation_list.html'
    invitation_class = PlanViewerInvitation
