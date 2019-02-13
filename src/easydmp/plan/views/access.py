import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic import (
    UpdateView,
    ListView,
    DeleteView,
)
from easydmp.common.views.mixins import DeleteFormMixin
from easydmp.invitation.models import PlanInvitation

from ..models import Plan
from ..models import PlanAccess
from ..forms import PlanAccessForm
from ..forms import ConfirmOwnPlanAccessChangeForm


LOG = logging.getLogger(__name__)


# -- sharing plans


class PlanAccessView(UserPassesTestMixin, ListView):
    "View and change who has access to what"
    template_name = 'easydmp/plan/planaccess_list.html'
    model = PlanAccess

    def dispatch(self, request, *args, **kwargs):
        self.plan = self.get_plan()
        self.invitations = self.get_invitations()
        self.queryset = self.get_queryset()
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        if self.queryset.filter(user=self.request.user):
            return True
        return False

    def get_plan(self):
        plan_id = self.kwargs['plan']
        return Plan.objects.get(pk=plan_id)

    def get_queryset(self):
        return self.model.objects.filter(plan=self.plan)

    def get_invitations(self):
        usernames = self.get_queryset().values_list('user__username', flat=True)
        return PlanInvitation.objects.filter(
            plan=self.plan,
            used__isnull=True,
        ).exclude(
            email_address__in=usernames
        ).valid_only()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invitations'] = self.invitations
        context['plan'] = self.plan
        accesses = []
        for access in self.get_queryset():
            form = PlanAccessForm(initial={'access': access.access})
            access.form = form
            accesses.append(access)
        context['accesses'] = accesses
        return context

    def get_success_url(self):
        return reverse('share_plan', kwargs={'plan': self.plan.pk})


class UpdatePlanAccessView(UserPassesTestMixin, UpdateView):
    model = PlanAccess
    form_class = PlanAccessForm
    pk_url_kwarg = 'access'
    template_name = 'easydmp/plan/planaccess_confirm_update.html'
    changing_self = None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.request.user == self.object.user:
            self.changing_self = True
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        if self.get_object():
            return True
        return False

    def get_queryset(self):
        user_accesses = self.request.user.plan_accesses.filter(may_edit=True)
        plan_pks = user_accesses.values_list('plan__pk', flat=True)
        qs = self.model.objects.filter(plan__pk__in=plan_pks)
        return qs

    def get_form_class(self):
        if self.changing_self:
            return ConfirmOwnPlanAccessChangeForm
        return self.form_class

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if 'cancel' in self.request.POST or not form.is_valid():
            return self.form_invalid(form)
        if self.changing_self and 'submit' not in self.request.POST:
                return self.get(request, *args, **kwargs)
        return self.form_valid(form)

    def form_valid(self, form):
        access = form.cleaned_data['access']
        may_edit = False
        if access == 'view and edit':
            may_edit = True
        if may_edit != self.object.may_edit:
            self.object.may_edit = may_edit
            self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('share_plan', kwargs={'plan': self.object.plan.pk})


class DeletePlanAccessView(UserPassesTestMixin, DeleteFormMixin, DeleteView):
    "Delete a PlanAccess, leading to a person leaving a plan"

    model = PlanAccess
    template_name = 'easydmp/plan/planaccess_confirm_delete.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'access'

    def test_func(self):
        if self.get_object():
            return True
        return False

    def get_queryset(self):
        return self.request.user.plan_accesses.all()

    def delete(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return HttpResponseRedirect(self.get_success_url())
        return super().delete(request, *args, **kwargs)
