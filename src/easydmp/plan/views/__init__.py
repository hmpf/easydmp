from copy import deepcopy
import logging

from django.contrib import messages
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy, NoReverseMatch
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import HttpResponseServerError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import (
    CreateView,
    UpdateView,
    DetailView,
    ListView,
    DeleteView,
    FormView,
    RedirectView,
    TemplateView,
)
from weasyprint import HTML

from easydmp.lib.views.mixins import DeleteFormMixin
from easydmp.dmpt.models import Question, Section, Template
from easydmp.dmpt.forms import AbstractNodeFormSet
from easydmp.eventlog.models import EventLog
from easydmp.eventlog.utils import log_event

from ..import_plan import PlanImporter
from ..models import add_answerset
from ..models import AnswerHelper
from ..models import AnswerSet
from ..models import AnswerSetException
from ..models import Plan
from ..models import PlanAccess
from ..models import remove_answerset
from ..forms import ConfirmForm
from ..forms import SaveAsPlanForm
from ..forms import StartPlanForm
from ..forms import UpdatePlanForm
from ..forms import CrispyPlanImportForm


LOG = logging.getLogger(__name__)


def progress(so_far, all):
    "Returns percentage done, as float"
    return so_far/float(all)*100


def get_section_progress(plan, current_section):
    viewname = 'answerset_detail'
    sections = plan.template.sections.filter(section_depth=1).order_by('position')
    visited_sections = plan.visited_sections.all()
    section_struct = []
    current_section = current_section.get_topmost_section()
    for section in sections:
        answerset = section.answersets.filter(plan=plan).order_by('pk').first()
        kwargs = {'plan': plan.id, 'section': section.pk, 'answerset': answerset.pk}
        link = reverse(viewname, kwargs=kwargs)
        section_dict = {
            'label': section.label,
            'title': section.title,
            'full_title': section.full_title(),
            'pk': section.pk,
            'status': 'new',
            'link': link,
        }
        if section in visited_sections:
            section_dict['status'] = 'visited'
        if section == current_section:
            section_dict['status'] = 'active'
        section_struct.append(section_dict)
    return section_struct


def get_question(question_pk, template):
    # Ensure that the template does contain the question
    try:
        sections = template.sections.all()
        question = (Question.objects
            .select_related('section')
            .get(pk=question_pk, section__in=sections)
        )
    except Question.DoesNotExist as e:
        raise Http404(f"Unknown question id: {question_pk}")
    question = question.get_instance()
    return question


def update_data_for_additional_form_in_formset(form, post_data):
    if not isinstance(form, AbstractNodeFormSet):
        return
    prefix = form.prefix
    if f'{prefix}_add_row' not in post_data:
        return  # row not added
    data = post_data.copy()
    total_form_lookup = f'{prefix}-TOTAL_FORMS'
    data[total_form_lookup] = str(int(post_data[total_form_lookup]) + 1)
    return data


# -- plans


class ChooseTemplateForNewPlanView(ListView):
    """Choose a template before creating a new plan"""

    http_method_names = ['get', 'head', 'options', 'trace']
    template_name = 'easydmp/plan/template_list.html'
    model = Template

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        if qs.count() == 1:
            template = qs.get()
            return HttpResponseRedirect(
                reverse('create_plan', kwargs={'template_id': template.id})
            )
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        non_empty_templates = super().get_queryset().is_not_empty()
        return non_empty_templates.has_access(self.request.user)


class PlanAccessViewMixin:

    def get_queryset(self):
        return super().get_queryset().viewable(self.request.user)


class AnswerSetAccessViewMixin:

    def get_queryset(self):
        plans = Plan.objects.editable(self.request.user)
        return super().get_queryset().filter(plan__in=plans)


class AbstractPlanViewMixin:

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def existing_with_same_title(self):
        return self.model.objects.filter(template=self.object.template,
                                         title=self.object.title,)

    def find_existing(self):
        user = self.request.user
        qs = self.existing_with_same_title()
        if not qs:
            return None
        qs = qs.filter(accesses__user=user)
        if not qs:
            return None
        return qs


class StartPlanView(AbstractPlanViewMixin, PlanAccessViewMixin, CreateView):
    """Create a new empty plan from the given template"""
    model = Plan
    template_name = 'easydmp/plan/plan_start_form.html'
    form_class = StartPlanForm

    def get_template(self):
        tid = self.kwargs.get('template_id')
        try:
            template = Template.objects.get(id=tid)
        except Template.DoesNotExist:
            raise Http404("Template not found")
        if template.is_empty:
            LOG.warn('Accessing an empty template: %i', tid)
            raise Http404("Template not found")
        return template

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['template'] = self.get_template()
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.data = {}
        self.object.previous_data = {}
        existing = self.find_existing()
        if not existing:
            self.object.save()
            return HttpResponseRedirect(self.get_success_url())
        if existing.count() == 1:
            hop_to = existing[0]
            # send message
            return HttpResponseRedirect(reverse('plan_detail', kwargs={'plan': hop_to.pk}))
        # multiple plans with same editor, template and title exists
        return HttpResponseServerError()

    def get_success_url(self):
        submit_value = self.request.POST['submit']
        if submit_value == self.form_class.OVERVIEW:
            return reverse('plan_detail', kwargs={'plan': self.object.pk})
        first_question = self.object.get_first_question()
        first_section = first_question.section
        try:
            answerset = self.object.answersets.get(section=first_section)
        except AnswerSet.DoesNotExist:
            answerset = self.object.ensure_answersets(first_section)
        kwargs = {'plan': self.object.pk, 'answerset': answerset.pk}
        if first_question.section.branching:
            kwargs['question'] = first_question.pk
            success_urlname = 'answer_question'
        else:
            kwargs['section'] = first_section.pk
            success_urlname = 'answer_linear_section'
        return reverse(success_urlname, kwargs=kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template'] = self.get_template()
        return context


class UpdatePlanView(PlanAccessViewMixin, AbstractPlanViewMixin, UpdateView):
    "Update metadata about a plan"

    template_name = 'easydmp/plan/updateplan_form.html'
    model = Plan
    pk_url_kwarg = 'plan'
    form_class = UpdatePlanForm

    def get_success_url(self):
        kwargs = {
            'plan': self.object.pk,
        }
        return reverse('plan_detail', kwargs=kwargs)

    def form_valid(self, form):
        existing = self.find_existing()
        if not existing:
            self.object = form.save()
            return HttpResponseRedirect(self.get_success_url())
        if existing.count() == 1:
            hop_to = existing[0]
            # send message
            return HttpResponseRedirect(reverse('plan_detail', kwargs={'plan': hop_to.pk}))
        # multiple plans with same editor, template and title exists
        return HttpResponseServerError()


class DeletePlanView(PlanAccessViewMixin, DeleteFormMixin, DeleteView):
    "Delete an unpublished Plan"

    model = Plan
    template_name = 'easydmp/plan/plan_confirm_delete.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().unpublished()
        return qs.filter(added_by=self.request.user)

    def delete(self, request, *args, **kwargs):
        """Delete the plan and record who did it"""
        if 'cancel' in request.POST:
            return HttpResponseRedirect(self.get_success_url())
        # cannot use super().delete because then we cannot pass in the user
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete(request.user)
        return HttpResponseRedirect(success_url)


class SaveAsPlanView(PlanAccessViewMixin, UpdateView):
    "Save a copy of an existing plan as a new plan"

    model = Plan
    template_name = 'easydmp/plan/plan_confirm_save_as.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'plan'
    form_class = SaveAsPlanForm

    def get_queryset(self):
        qs = super().get_queryset()
        return qs

    def form_valid(self, form):
        title = form.cleaned_data['title']
        abbreviation = form.cleaned_data.get('abbreviation', '')
        keep_users = form.cleaned_data.get('keep_users', True)
        self.object.save_as(title, self.request.user, abbreviation, keep_users)
        return HttpResponseRedirect(self.get_success_url())


class ValidatePlanView(PlanAccessViewMixin, UpdateView):
    "Validate an entire plan"

    template_name = 'easydmp/plan/plan_confirm_validate.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().invalid()
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.validate(request.user, recalculate=True, commit=True)
        return HttpResponseRedirect(success_url)


class LockPlanView(PlanAccessViewMixin, UpdateView):
    "Lock a plan to make it read only"

    template_name = 'easydmp/plan/plan_confirm_lock.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().unlocked()
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.lock(request.user)
        return HttpResponseRedirect(success_url)


class PublishPlanView(PlanAccessViewMixin, UpdateView):
    """Publish a plan

    This makes it read only and undeletable.
    """

    template_name = 'easydmp/plan/plan_confirm_publish.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().valid().locked()
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.publish(request.user)
        return HttpResponseRedirect(success_url)


class CreateNewVersionPlanView(PlanAccessViewMixin, UpdateView):
    """Create a new version of a plan

    This reopens a read only or published plan, incrementng the version number.

    """

    template_name = 'easydmp/plan/plan_confirm_createnewversion.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().locked()
        return qs

    def get_success_url(self):  # Not used, url generated in post()
        pass

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        new = self.object.create_new_version(request.user)
        success_url = reverse('plan_detail', kwargs={'plan': new.pk})
        return HttpResponseRedirect(success_url)


class ExportPlanView(PlanAccessViewMixin, DetailView):
    template_name = 'easydmp/plan/plan_export.html'
    model = Plan
    pk_url_kwarg = 'plan'

    def get_context_data(self, **kwargs):
        pk = self.object.pk
        html = reverse('generated_plan_html', kwargs={'plan': pk})
        pdf = reverse('generated_plan_pdf', kwargs={'plan': pk})
        easydmp = reverse('v2:plan-export', kwargs={'pk': pk, 'format': 'json'})
        rdadcs = reverse('v2:plan-export-rda', kwargs={'pk': pk})
        kwargs['export'] = {
            'html': html,
            'pdf': pdf,
            'easydmp': easydmp,
            'rdadcs': rdadcs,
        }
        return kwargs


class ImportPlanView(PlanAccessViewMixin, FormView):
    template_name = 'easydmp/plan/plan_import_form.html'
    form_class = CrispyPlanImportForm
    pim = None

    def form_valid(self, form):
        importer = PlanImporter(self.request, via='frontend')
        self.pim = importer.import_plan()
        importer.message()
        if self.pim:
            importer.audit_log()
            return HttpResponseRedirect(self.get_success_url())
        return self.form_invalid(form)

    def get_success_url(self):
        success_url = reverse('plan_detail', kwargs={'plan': self.pim.plan.pk})
        return success_url


class AddAnswerSetView(RedirectView):

    def get(self, request, *args, **kwargs):
        self.section = get_object_or_404(Section, pk=self.kwargs['section'])
        self.plan = get_object_or_404(Plan, pk=self.kwargs['plan'])
        sibling_id = self.kwargs.get('answerset', None)
        self.sibling = None
        if sibling_id:
            self.sibling = get_object_or_404(AnswerSet, pk=sibling_id)
        editable = self.plan.may_edit(request.user)
        if not editable:
            raise Http404  # go away, peon

        try:
            answerset = add_answerset(self.section, self.plan, self.sibling)
        except (AnswerSetException, AnswerSet.MultipleObjectsReturned) as e:
            raise HttpResponseBadRequest(e)
        if not answerset:
            messages.warning(request, "Answerset not added, invalid action")
            url = self.get_failure_url(*args, **kwargs)
            return HttpResponseRedirect(url)
        self.next_answerset = answerset
        url = self.get_redirect_url(*args, **kwargs)

        template = '{timestamp} {actor} added answerset "{action_object}" to plan {target}'
        log_event(request.user, 'add-answerset', target=self.plan,
                  object=self.next_answerset, template=template)
        messages.success(request, "Answerset added")
        return HttpResponseRedirect(url)

    def get_failure_url(self, *args, **kwargs):
        return reverse('plan_detail', kwargs={'plan': self.plan.pk})

    def get_redirect_url(self, *args, **kwargs):
        minimal_kwargs = {'plan': self.next_answerset.plan_id, 'answerset': self.next_answerset.id}
        if self.next_answerset.section.branching:
            viewname = 'answer_question'
            kwargs = dict(
                question=self.next_answerset.section.first_question.id,
                **minimal_kwargs,
            )
            return reverse(viewname, kwargs=kwargs)
        else:
            viewname = 'answer_linear_section'
            kwargs = dict(
                section=self.next_answerset.section_id,
                **minimal_kwargs,
            )
            return reverse(viewname, kwargs=kwargs)


class AnswerSetSectionMixin(AnswerSetAccessViewMixin):

    def check_and_get_kwargs(self, request):
        self.answerset = super().get_object()
        self.plan = self.answerset.plan
        correct_plan = self.plan.pk == self.kwargs['plan']
        self.section = self.answerset.section
        correct_section = self.section.pk == self.kwargs['section']
        viewable = self.plan.may_view(request.user)
        self.editable = self.plan.may_edit(request.user)
        if not all((correct_plan, correct_section, viewable)):
            raise Http404


class RemoveAnswerSetView(DeleteFormMixin, AnswerSetSectionMixin, DeleteView):
    model = AnswerSet
    pk_url_kwarg = 'answerset'
    template_name = 'easydmp/plan/answerset_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.check_and_get_kwargs(request)
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        success_url = self.get_success_url()
        template = '{timestamp} {actor} removed answerset "{action_object}" from plan {target}'
        log_event(request.user, 'remove-answerset', target=self.plan,
                  object=self.answerset, template=template)
        try:
            remove_answerset(self.answerset)
        except AnswerSetException as e:
            raise HttpResponseBadRequest(e)
        messages.success(request, 'Answerset removed')
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.plan.id})


class GetAnswerSetView(AnswerSetSectionMixin, DetailView):
    ACTIONS = set(('next', 'prev', 'current', 'skip_to_next', 'skip_to_prev'))
    model = AnswerSet
    pk_url_kwarg = 'answerset'
    viewname = 'answer_linear_section'
    branching_viewname = 'answer_question'

    def get(self, request, *args, **kwargs):
        self.check_and_get_kwargs(request)
        action = self.kwargs['action']
        if not action in self.ACTIONS:
            raise Http404
        method = getattr(self, f'get_{action}', None)

        self.plan_pk = self.plan.pk
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.answerset, template=template)
        url = method()
        return redirect(url)

    def get_url(self, question_pk, answerset):
        kwargs = dict(plan=self.plan_pk, answerset=answerset.pk)
        if answerset.section.branching:
            viewname = self.branching_viewname
            kwargs['question'] = question_pk
        else:
            viewname = self.viewname
            kwargs['section'] = answerset.section.pk
        return reverse(viewname, kwargs=kwargs)

    def get_summary(self):
        return reverse('plan_detail', kwargs={'plan': self.plan_pk})

    def get_next(self):
        next_section = self.section.get_next_nonempty_section()
        if not next_section:
            return self.get_summary()

        answerset = self.answerset.get_next_answerset()
        return self.get_url(answerset.section.first_question.pk, answerset)

    get_skip_to_next = get_next

    def get_prev(self):
        prev_section = self.section.get_prev_nonempty_section()
        if not prev_section:
            return self.get_summary()

        answerset = self.answerset.get_prev_answerset()
        return self.get_url(answerset.section.last_question.pk, answerset)

    get_skip_to_prev = get_prev

    def get_current(self):
        answerset = self.answerset.get_prev_answerset()
        return self.get_url(self.section.first_question.pk, self.answerset)


class AnswerLinearSectionView(AnswerSetSectionMixin, DetailView):
    ACTIONS = ['save', 'next', 'skip_to_next', 'prev', 'skip_to_prev']
    template_name = 'easydmp/plan/answer_linear_section_form.html'
    model = AnswerSet
    pk_url_kwarg = 'answerset'
    viewname = 'answer_linear_section'
    branching_viewname = 'answer_question'
    __LOG = logging.getLogger('{}.{}'.format(__name__, 'AnswerLinearSectionView'))

    def dispatch(self, request, *args, **kwargs):
        error_message_404 = "This Section cannot be edited in one go"
        self.check_and_get_kwargs(request)

        # Chcek that the section is not branching
        # Explicit check
        if self.section.branching:
            # TODO: Jump to first question of section with AnswerQuestionView
            raise Http404(error_message_404)
        self.questions = (
            self.section.questions
            .filter(on_trunk=True)
            .order_by('position')
        )
        # Implicit check: all questions must be on_trunk
        if self.section.questions.count() != self.questions.count():
            # TODO: Jump to first question of section with AnswerQuestionView
            raise Http404(error_message_404)

        self.prev_section = self.section.get_prev_section()
        self.next_section = self.section.get_next_section()
        self.modified_by = request.user
        self.plan_pk = self.plan.pk
        self.object = self.plan
        self.answers = [AnswerHelper(question, self.answerset) for question in self.questions]
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.section, template=template)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        for action in self.ACTIONS:
            if self.request.POST.get(action, None):
                if action == 'save':
                    action == 'current'
                return self.get_url(action)
        # Summary
        return reverse('plan_detail', kwargs={'plan': self.plan_pk})

    def get_url(self, action):
        kwargs = dict(
            section=self.section.pk,
            answerset=self.answerset.pk,
            plan=self.plan_pk,
        )
        kwargs['action'] = 'current'  # safe default, reached by "save"
        if action in self.ACTIONS[1:]:
            kwargs['action'] = action
        url = reverse("get_answerset", kwargs=kwargs)
        return url

    def get(self, _request, *args, **kwargs):
        forms = self.get_forms()
        return self.render_to_response(self.get_context_data(forms=forms))

    def add_form_to_formset(self, post_data, forms):
        for formdict in forms:
            form = formdict['form']
            data = update_data_for_additional_form_in_formset(form, post_data)
            if data:
                break
        else:
            return  # no formsets found or no add_row command

        # Generate all forms with new data
        form_kwargs = self.get_form_kwargs()
        new_forms = []
        for formdict in forms:
            answer = formdict['answer']
            new_formdict = self._get_form(answer, form_kwargs, data=data)
            new_forms.append(new_formdict)
        return self.render_to_response(self.get_context_data(forms=new_forms))

    def post(self, request, *args, **kwargs):
        forms = self.get_forms()
        response = self.add_form_to_formset(request.POST, forms)
        if response:
            return response
        template = '{timestamp} {actor} updated {action_object} of {target}'
        log_event(request.user, 'update section', target=self.plan,
                  object=self.section, template=template)
        if all([question['form'].is_valid() for question in forms]):
            return self.forms_valid(forms)
        else:
            return self.forms_invalid(forms)

    def forms_valid(self, forms):
        prev_data = deepcopy(self.answerset.data)
        for question in forms:
            answer = question['answer']
            form = question['form']
            notesform = question['notesform']
            changed_condition = answer.update_answer_via_forms(
                form,
                notesform,
                self.request.user,
            )
            if changed_condition:
                self.__LOG.debug('form_valid: q%s/p%s: change saved',
                                 answer.question_id, self.object.pk)
            else:
                self.__LOG.debug('form_valid: q%s/p%s: condition not changed',
                                 answer.question_id, self.object.pk)
        if prev_data != self.answerset.data:
            self.answerset.validate()
            self.plan.modified_by = self.request.user
            self.plan.save(user=self.request.user)
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, forms):
        skip = self.request.POST.get('skip', None)
        if skip:
            url = self.get_url('skip')
            return HttpResponseRedirect(url)
        return self.render_to_response(self.get_context_data(forms=forms))

    def get_form_kwargs(self):
        kwargs = {}
        if self.request.method in ('POST', 'PUT'):
            kwargs['data'] = self.request.POST
        return kwargs

    def _get_form(self, answer, form_kwargs, data=None):
        if data:
            form_kwargs['data'] = data
        initial = answer.get_initial()
        form = answer.get_form(initial=initial, **form_kwargs)
        notesform = answer.get_notesform(initial=initial, **form_kwargs)
        return {
            'form': form,
            'notesform': notesform,
            'answer': answer,
        }

    def get_forms(self):
        form_kwargs = self.get_form_kwargs()
        forms = []
        for answer in self.answers:
            forms.append(self._get_form(answer, form_kwargs))
        return forms

    def get_button_context(self):
        # Next/Prev/Save/Summary/Skip
        prev = {
            'name': 'prev',
            'value': 'Prev',
            'primary': True,
            'tooltip': "Save the form then go to the previous section",
        }
        prev_summary = {
            'name': 'prev',
            'value': 'Summary',
            'primary': True,
            'tooltip': "Save the form then go to the summary",
        }
        save = {
            'name': 'save',
            'value': 'Save',
            'primary': True,
            'tooltip': "Save the form",
        }
        next = {
            'name': 'next',
            'value': 'Next',
            'primary': True,
            'tooltip': "Save the form then go to the next section",
        }
        next_summary = {
            'name': 'next',
            'value': 'Summary',
            'primary': True,
            'tooltip': "Save the form then go to the summary",
        }
        skip_to_prev = {
            'name': 'skip_to_prev',
            'value': '< Skip',
            'primary': False,
            'tooltip': "Go to the prev section without saving",
        }
        skip_to_prev_summary = {
            'name': 'skip_to_prev',
            'value': '< Summary',
            'primary': False,
            'tooltip': "Go to the summary without saving",
        }
        skip_to_next = {
            'name': 'skip_to_next',
            'value': 'Skip >',
            'primary': False,
            'tooltip': "Go to the next section without saving",
        }
        skip_to_next_summary = {
            'name': 'skip_to_next',
            'value': 'Summary >',
            'primary': False,
            'tooltip': "Go to the summary without saving",
        }
        if self.prev_section and self.next_section:
            buttons = (prev, save, next)
            skip_to_prev_button = skip_to_prev
            skip_to_next_button = skip_to_next
        elif self.prev_section and not self.next_section:
            buttons = (prev, save, next_summary)
            skip_to_prev_button = skip_to_prev
            skip_to_next_button = skip_to_next_summary
        elif self.next_section and not self.prev_section:
            buttons = (prev_summary, save, next)
            skip_to_prev_button = skip_to_prev_summary
            skip_to_next_button = skip_to_next
        else:
            buttons = (save,)
            skip_to_prev_button = None
            skip_to_next_button = skip_to_next_summary

        # Add/remove buttons
        num_answersets = self.answerset.get_full_siblings().count() - 1
        deletable_if_optional = self.section.optional and num_answersets
        deletable_if_repeatable = self.section.repeatable and num_answersets > 1
        addable_if_optional = self.section.optional and not num_answersets
        addable_if_repeatable = self.section.repeatable
        addable = bool(addable_if_repeatable or addable_if_optional)
        deletable = bool(deletable_if_optional or deletable_if_repeatable)
        return {
            'traversal_buttons': buttons,
            'skip_to_prev': skip_to_prev_button,
            'skip_to_next': skip_to_next_button,
            'addable': addable,
            'deletable': deletable,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs).copy()
        context['section'] = self.section
        context['answerset'] = self.answerset
        context['prev_section'] = self.prev_section
        context['next_section'] = self.next_section
        context['section_progress'] = get_section_progress(self.plan, self.section)
        context['forms'] = kwargs.get('forms', self.get_forms())
        context.update(self.get_button_context())
        return context

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


class RedirectToAnswerQuestionView(RedirectView):
    permanent = True
    pattern_name = 'answer_question'

    def get_redirect_url(self, *args, **kwargs):
        plan_pk = kwargs['plan']
        try:
            plan = Plan.objects.get(id=plan_pk)
        except Plan.DoesNotExist:
            raise Http404
        question_pk = kwargs['question']
        try:
            question = Question.objects.get(id=question_pk)
        except Question.DoesNotExist:
            raise Http404
        answersets = plan.answersets.filter(section=question.section)
        answerset = answersets.order_by('pk').first()
        kwargs['answerset'] = int(answerset.pk)
        return super().get_redirect_url(*args, **kwargs)


class GetAnswerView(AnswerSetAccessViewMixin, DetailView):
    ACTIONS = set(('next', 'prev', 'current'))
    model = AnswerSet
    pk_url_kwarg = 'answerset'
    viewname = 'answer_linear_section'
    branching_viewname = 'answer_question'
    __LOG = logging.getLogger('{}.{}'.format(__name__, 'GetAnswerView'))

    def check_and_get_kwargs(self, request):
        self.answerset = super().get_object()
        self.plan = self.answerset.plan
        correct_plan = self.plan.pk == self.kwargs['plan']
        self.section = self.answerset.section
        viewable = self.plan.may_view(request.user)
        self.editable = self.plan.may_edit(request.user)
        if not all((correct_plan, viewable)):
            raise Http404
        self.question_pk = self.kwargs.get('question')
        self.question = get_question(self.question_pk, self.plan.template)
        self.answer = AnswerHelper(self.question, self.answerset)

    def get(self, request, *args, **kwargs):
        error_message_404 = "This Section cannot be edited in one go"
        self.check_and_get_kwargs(request)
        action = self.kwargs['action']
        if not action in self.ACTIONS:
            raise Http404
        method = getattr(self, f'get_{action}', None)

        self.plan_pk = self.plan.pk
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.answerset, template=template)
        url = method()
        return redirect(url)

    def get_url(self, question, answerset):
        kwargs = {
            'plan': self.plan.pk,
            'question': question.pk,
            'answerset': answerset.pk,
        }
        self.__LOG.debug('Going to question "%s"', kwargs['question'])
        return reverse(self.branching_viewname, kwargs=kwargs)

    def get_summary(self):
        return reverse('plan_detail', kwargs={'plan': self.plan_pk})

    def get_current(self):
        return self.get_url(self.question, self.answerset)

    def get_next(self):
        data = self.answerset.data
        next_question = self.question.get_next_question(data)
        if not next_question:
            # Finished answering all questions
            return self.get_summary()
        plan_kwargs = {'plan': self.plan.pk}
        answerset = self.answerset
        if next_question.section != self.section:
            answerset = self.answerset.get_next_answerset()
        return self.get_url(next_question, answerset)

    def get_prev(self):
        data = self.answerset.data
        prev_question = self.question.get_prev_question(data)
        if not prev_question:
            # Clicked prev on very first question
            return self.get_summary_url()
        answerset = self.answerset
        if prev_question.section != self.section:
            answerset = self.answerset.get_prev_answerset()
        return self.get_url(prev_question, answerset)


class AnswerQuestionView(AnswerSetAccessViewMixin, UpdateView):
    "Answer a Question"

    model = AnswerSet
    template_name = 'easydmp/plan/answer_question_form.html'
    pk_url_kwarg = 'answerset'
    fields = ('plan_name', 'data')
    __LOG = logging.getLogger('{}.{}'.format(__name__, 'AnswerQuestionView'))

    def check_and_get_kwargs(self):
        """Store frequently used values as early as possible

        Prevents multiple database-queries to fetch known data.
        """
        self.plan_pk = self.kwargs.get('plan')
        plans = (Plan.objects
                 .select_related('template')
                 .prefetch_related('template__sections', 'answersets'))
        try:
            self.plan = plans.get(id=self.plan_pk)
        except Plan.DoesNotExist:
            raise Http404(f'Plan {self.plan_pk} does not exist. Invalid id?')

        self.template = self.plan.template
        self.answerset = super().get_object()
        self.object = self.answerset
        self.question_pk = self.kwargs.get('question')
        self.question = get_question(self.question_pk, self.template)
        self.answer = AnswerHelper(self.question, self.answerset)
        self.section = self.question.section
        self.prev_section = self.section.get_prev_section()
        self.next_section = self.section.get_next_section()

    def dispatch(self, request, *args, **kwargs):
        self.check_and_get_kwargs()
        return super().dispatch(request, *args, **kwargs)

    def set_referer(self, request):
        self.referer = request.META.get('HTTP_REFERER', None)

    def get_initial(self):
        return self.answer.get_initial()

    def get_summary_url(self):
        return reverse('plan_detail', kwargs={'plan': self.plan.pk})

    def get_success_url(self):
        kwargs = dict(
            answerset=self.answerset.pk,
            plan=self.plan_pk,
            question=self.question.pk,
        )
        action = None
        for action in ('save', 'next', 'prev'):
            if action in self.request.POST:
                kwargs['action'] = action if action != 'save' else 'current'
                return reverse('get_answer', kwargs=kwargs)
        # Stay on same page if not explicitly going elsewhere
        return self.get_url(self.question, self.answerset)

    def get_context_data(self, **kwargs):
        question = self.question
        section = self.section
        path = section.questions.order_by('position')
        context = kwargs.copy()
        context['object'] = self.get_object()  # SingleObjectMixin
        # FormMixin
        context['form'] = kwargs.get('form', self.get_form())
        context['notesform'] = kwargs.get('notesform', self.get_notesform())
        context['plan'] = self.plan
        context['path'] = path
        context['question'] = question
        context['question_pk'] = question.pk
        context['label'] = question.label
        context['answers'] = question.canned_answers.order().values()
        context['framing_text'] = question.framing_text
        context['section'] = section
        neighboring_questions = Question.objects.filter(section=section)
        context['questions_in_section'] = neighboring_questions
        num_questions = neighboring_questions.count()
        num_questions_so_far = len(question.get_all_preceding_questions())
        context['progress'] = progress(num_questions_so_far, num_questions)
        context['referrer'] = self.referer  # Not a typo! From the http header
        context['section_progress'] = get_section_progress(self.plan, section)
        return super().get_context_data(**context)

    def get_prefix(self):
        return self.answer.prefix

    def get_notesform(self, **_):
        form_kwargs = self.get_form_kwargs()
        form = self.answer.get_notesform(**form_kwargs)
        return form

    def _get_form(self, **kwargs):
        form_kwargs = self.get_form_kwargs()
        question = self.question
        generate_kwargs = {
            'has_prevquestion': question.has_prev_question(),
        }
        generate_kwargs.update(form_kwargs)
        generate_kwargs.update(kwargs)
        form = self.answer.get_form(**generate_kwargs)
        return form

    def get_form(self, **_):
        form = self._get_form()
        return form

    def get(self, request, *args, **kwargs):
        self.set_referer(request)
        self.__LOG.debug('GET-ing q%s/p%s', self.question_pk, self.plan.pk)
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.question, template=template)
        return super().get(request, *args, **kwargs)

    def add_form_to_formset(self, request, form, *args, **kwargs):
        data = update_data_for_additional_form_in_formset(form, request.POST)
        if not data:
            return
        formset = self._get_form(data=data)
        notesform = self.get_notesform(data=data)
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data(
            form=formset,
            notesform=notesform,
        ))

    def post(self, request, *args, **kwargs):
        self.set_referer(request)
        self.__LOG.debug('POST-ing q%s/p%s', self.question_pk, self.plan.pk)
        form = self.get_form()
        response = self.add_form_to_formset(request, form)  # May redirect to a GET
        if response:
            return response
        notesform = self.get_notesform()
        if form.is_valid() and notesform.is_valid():
            self.request = request
            return self.form_valid(form, notesform)
        else:
            return self.form_invalid(form, notesform)

    def form_valid(self, form, notesform):
        self.__LOG.debug('form_valid: q%s/p%s: valid', self.question_pk, self.plan.pk)
        changed_condition = self.answer.update_answer_via_forms(
            form,
            notesform,
            self.request.user,
        )
        self.plan = self.get_object().plan  # Refresh
        if changed_condition:
            self.__LOG.debug('form_valid: q%s/p%s: change saved',
                             self.question_pk, self.plan.pk)
            if self.question.branching_possible:
                self.__LOG.debug('form_valid: q%s/p%s: checking for unreachable answers',
                                 self.question_pk, self.plan.pk)
                self.answerset.hide_unreachable_answers_after(self.question)
                self.answerset.validate()
        else:
            self.__LOG.debug('form_valid: q%s/p%s: condition not changed', self.question.pk, self.plan.pk)
        template = '{timestamp} {actor} updated {action_object} of {target}'
        log_event(self.request.user, 'update', target=self.plan,
                  object=self.question, template=template)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, notesform):
        self.__LOG.debug('q%s/p%s: INvalid', self.question_pk, self.plan.pk)
        self.answer.set_invalid()
        return self.render_to_response(
            self.get_context_data(form=form, notesform=notesform))


class FirstQuestionView(PlanAccessViewMixin, RedirectView):
    "Go to the first Question of a Plan"

    def get_redirect_url(self, *args, **kwargs):
        plan_pk = self.kwargs.get('plan')
        plan = Plan.objects.get(pk=plan_pk)
        question_pk = plan.get_first_question().pk
        url = reverse(
            'answer_question',
            kwargs={'plan': plan_pk, 'question': question_pk}
        )
        return url


class PlanListView(ListView):
    "List all plans for a user"

    model = Plan
    template_name = 'easydmp/plan/plan_list.html'

    def has_superpowers(self):
        return 'superpowers' in self.request.GET

    def get_queryset(self):
        qs = super().get_queryset().viewable(
            self.request.user,
            superpowers=self.has_superpowers(),
            include_public=False,
        )
        return qs.order_by('-added')

    def get(self, request, *args, **kwargs):
        next = super().get(request, *args, **kwargs)
        template = '{timestamp} {actor} listed plans'
        log_event(request.user, 'list plan', template=template)
        return next


class PlanDetailView(PlanAccessViewMixin, DetailView):
    "Show an overview of a plan"
    model = Plan
    pk_url_kwarg = 'plan'
    template_name = 'easydmp/plan/plan_detail.html'
    login_required = False  # Public plans are accessible to all

    def get_context_data(self, **kwargs):
        editable = self.object.may_edit(self.request.user) and not self.object.locked
        context = {
            'output': self.object.get_nested_summary(),
            'plan': self.object,
            'template': self.object.template,
            'editable_for_user': editable,
        }
        context.update(**kwargs)
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        next = super().get(request, *args, **kwargs)
        self.object.validate(request.user, recalculate=False, commit=True)
        template = '{timestamp} {actor} accessed {target}'
        log_event(request.user, 'access', target=self.object,
                  template=template)
        return next


def generate_pretty_exported_plan(plan, template_name):
    editors = [access.user for access in
               PlanAccess.objects.filter(plan=plan).filter(may_edit=True)]

    context = plan.get_context_for_generated_text()
    context['text'] = plan.get_nested_canned_text()
    context['logs'] = EventLog.objects.any(plan)
    context['reveal_questions'] = plan.template.reveal_questions
    context['editors'] = ', '.join([str(ed) for ed in editors])
    context['last_validated_ok'] = plan.last_validated if plan.valid else '-'

    return render_to_string(template_name, context)


class AbstractGeneratedPlanView(DetailView):
    model = Plan
    pk_url_kwarg = 'plan'
    login_required = False

    def get_queryset(self):
        "Show published plans to the public, otherwise only viewable"
        return self.model.objects.viewable(self.request.user, include_public=True)

    def generate_exported_plan(self):
        self.object = self.get_object()
        template = self.get_template_names()[0]
        self.export = generate_pretty_exported_plan(self.object, template)

    def log(self, request):
        if request.user.is_authenticated:
            template = '{timestamp} {actor} accessed generated version of {target}'
            log_event(request.user, 'access generated plan', target=self.object,
                      template=template)

    def get(self, request, *args, **kwargs):
        self.generate_exported_plan()
        self.log(request)
        response = HttpResponse(self.export, content_type=self.content_type)
        return response


class GeneratedPlanHTMLView(AbstractGeneratedPlanView):
    "Generate canned HTML of a plan"

    template_name = 'easydmp/plan/generated_plan.html'


# XXX: Remove
class GeneratedPlanPlainTextView(AbstractGeneratedPlanView):
    "Generate canned plaintext of a Plan"

    template_name = 'easydmp/plan/generated_plan.txt'
    content_type = 'text/plain; charset=UTF-8'


class GeneratedPlanPDFView(AbstractGeneratedPlanView):
    "Generate canned PDF of a plan"

    template_name = 'easydmp/plan/generated_plan.html'
    content_type = 'application/pdf'

    def get(self, request, *args, **kwargs):
        self.generate_exported_plan()
        self.log(request)
        result = HTML(string=self.export).write_pdf()
        response = HttpResponse(content_type=self.content_type)
        response['Content-Disposition'] = 'inline; filename={}'.format(
            request.GET.get('filename') or '{}.pdf'.format(self.object.pk))
        response['Content-Transfer-Encoding'] = 'binary'
        response.write(result)
        return response


class AnswerSetDetailView(AnswerSetSectionMixin, DetailView):
    """Show an answerset

    Mostly relevant for sections without questions, ergo where the answerset
    will always be empty. If there *are* question, redirect to the correct
    update-view.
    """

    model = AnswerSet
    pk_url_kwarg = 'answerset'
    template_name = 'easydmp/plan/answerset_detail.html'

    def get(self, request, *args, **kwargs):
        self.check_and_get_kwargs(request)

        # Set visited empty section
        self.plan.visited_sections.add(self.section)
        topmost = self.section.get_topmost_section()
        if topmost:
            self.plan.visited_sections.add(topmost)

        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.section, template=template)

        if not self.section.questions.exists():
            # Show page for empty answerset
            return super().get(request, *args, **kwargs)

        question = self.section.first_question
        # Redirect to correct update-view if any questions
        if self.editable:
            if self.section.branching:
                view_name = 'answer_question'
                kwargs = {'question': question.pk}
            else:
                view_name = 'answer_linear_section'
                kwargs = {'section': self.section.pk}
            return redirect(
                view_name,
                plan=self.plan.pk,
                answerset=self.answerset.pk,
                **kwargs,
            )

        try:
            return redirect('plan_detail', kwargs={'plan': self.plan.pk})
        except NoReverseMatch:
            # This shouldn't happen unless a plan has been deleted behind our
            # backs or something
            LOG.warn('Failed accessing plan %i details while in that plan. Race condition? (User %s)',
                     self.plan, request.user)
            raise Http404

    def next(self):
        "Generate link to next page"
        plan_pk = self.plan.pk
        next_section = self.section.get_next_section()
        kwargs = {'plan': plan_pk}
        if next_section is not None:
            if self.editable:
                answerset = self.plan.get_answersets_for_section(next_section).first()
                kwargs['answerset'] = answerset.pk
                # Has questions
                question = next_section.first_question
                if question:
                    kwargs['question'] = question.pk
                    return reverse('answer_question', kwargs=kwargs)
                # Empty section
                kwargs['section'] = next_section.pk
                return reverse('answerset_detail', kwargs=kwargs)
        return reverse('plan_detail', kwargs=kwargs)

    def prev(self):
        "Generate link to previous page"
        plan_pk = self.plan.pk
        prev_section = self.section.get_prev_section()
        kwargs = {'plan': plan_pk}
        if prev_section is not None:
            if self.editable:
                answerset = self.plan.get_answersets_for_section(prev_section).last()
                kwargs['answerset'] = answerset.pk
                # Has questions
                question = prev_section.first_question
                if question:
                    kwargs['question'] = question.pk
                    return reverse('answer_question', kwargs=kwargs)
                # Empty section
                kwargs['section'] = prev_section.pk
                return reverse('answerset_detail', kwargs=kwargs)
        return reverse('plan_detail', kwargs=kwargs)

    def get_context_data(self, **kwargs):
        context = {
            'plan': self.plan,
            'next': self.next(),
            'prev': self.prev(),
            'section': self.section,
            'section_progress': get_section_progress(self.plan, self.section),
        }
        context.update(**kwargs)
        return super().get_context_data(**context)
