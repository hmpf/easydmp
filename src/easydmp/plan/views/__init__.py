from copy import deepcopy
import logging

from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseRedirect, Http404, HttpResponseServerError, HttpResponse
from django.shortcuts import redirect
from django.views.generic import (
    CreateView,
    UpdateView,
    DetailView,
    ListView,
    DeleteView,
    RedirectView,
)
from weasyprint import HTML

from easydmp.lib.views.mixins import DeleteFormMixin
from easydmp.dmpt.forms import make_form, NotesForm
from easydmp.dmpt.models import Question, Section, Template
from easydmp.eventlog.models import EventLog
from easydmp.eventlog.utils import log_event

from ..models import AnswerHelper, PlanAccess
from ..models import Plan
from ..forms import ConfirmForm
from ..forms import SaveAsPlanForm
from ..forms import StartPlanForm
from ..forms import UpdatePlanForm


LOG = logging.getLogger(__name__)


def progress(so_far, all):
    "Returns percentage done, as float"
    return so_far/float(all)*100


def get_section_progress(plan, current_section=None):
    sections = plan.template.sections.filter(section_depth=1).order_by('position')
    visited_sections = plan.visited_sections.all()
    section_struct = []
    current_section = current_section.get_topmost_section()
    for section in sections:
        section_dict = {
            'label': section.label,
            'title': section.title,
            'full_title': section.full_title(),
            'pk': section.pk,
            'status': 'new',
        }
        if section in visited_sections:
            section_dict['status'] = 'visited'
        if section == current_section:
            section_dict['status'] = 'active'
        section_struct.append(section_dict)
    return section_struct


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
        return super().get_queryset().has_access(self.request.user)


class PlanAccessViewMixin:

    def get_queryset(self):
        return super().get_queryset().viewable(self.request.user)


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
        try:
            return Template.objects.get(id=self.kwargs.get('template_id'))
        except Template.DoesNotExist:
            raise Http404("Template not found")

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
        kwargs = {'plan': self.object.pk}
        first_question = self.object.get_first_question()
        if first_question.section.branching:
            kwargs['question'] = first_question.pk
            success_urlname = 'new_question'
        else:
            kwargs['section'] = first_question.section.pk
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
        qs = super().get_queryset().valid()
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


class UpdateLinearSectionView(PlanAccessViewMixin, DetailView):
    template_name = 'easydmp/plan/plan_section_update.html'
    model = Plan
    pk_url_kwarg = 'plan'
    __LOG = logging.getLogger('{}.{}'.format(__name__, 'UpdateLinearSectionView'))

    def dispatch(self, request, *args, **kwargs):
        error_message_404 = "This Section cannot be edited in one go"
        self.section_pk = kwargs['section']
        # Check that the section is not branching
        try:
            self.section = (
                Section.objects
                    .prefetch_related('questions')
                    .get(branching=False, pk=self.section_pk)
            )
        except Section.DoesNotExist:
            # TODO: Jump to first question of section with NewQuestionView
            raise Http404(error_message_404)
        self.questions = (
            self.section.questions
            .filter(on_trunk=True)
            .order_by('position')
        )
        # Check that all questions are on_trunk
        if self.section.questions.count() != self.questions.count():
            # TODO: Jump to first question of section with NewQuestionView
            # Not a linear section
            raise Http404(error_message_404)
        self.prev_section = self.section.get_prev_section()
        self.next_section = self.section.get_next_section()
        self.modified_by = request.user
        self.plan_pk = kwargs[self.pk_url_kwarg]
        self.plan = self.get_object()
        self.object = self.plan
        self.answers = [AnswerHelper(question, self.plan) for question in self.questions]
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=self.section, template=template)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        default_kwargs = {'plan': self.plan_pk}
        if 'save' in self.request.POST:
            if self.next_section and self.next_section.branching:
                kwargs=dict(question=self.next_section.first_question.pk, **default_kwargs)
                viewname = 'new_question'
            else:
                kwargs = dict(section=self.section.pk, **default_kwargs)
                viewname = 'answer_linear_section'
            return reverse(viewname, kwargs=kwargs)
        if 'next' in self.request.POST and self.next_section:
            if self.next_section and self.next_section.branching:
                kwargs=dict(question=self.next_section.first_question.pk, **default_kwargs)
                viewname = 'new_question'
            else:
                kwargs = dict(section=self.next_section.pk, **default_kwargs)
                viewname = 'answer_linear_section'
            return reverse(viewname, kwargs=kwargs)
        if 'prev' in self.request.POST and self.prev_section:
            if self.prev_section.branching:
                kwargs=dict(question=self.prev_section.last_question.pk, **default_kwargs)
                viewname = 'new_question'
            else:
                kwargs = dict(section=self.prev_section.pk, **default_kwargs)
                viewname = 'answer_linear_section'
            return reverse(viewname, kwargs=kwargs)
        return reverse('plan_detail', kwargs={'plan': self.plan_pk})

    def get(self, _request, *args, **kwargs):
        forms = self.get_forms()
        return self.render_to_response(self.get_context_data(forms=forms))

    def post(self, request, *args, **kwargs):
        forms = self.get_forms()
        template = '{timestamp} {actor} updated {action_object} of {target}'
        log_event(request.user, 'update section', target=self.plan,
                  object=self.section, template=template)
        if all([question['form'].is_valid() for question in forms]):
            return self.forms_valid(forms)
        else:
            return self.forms_invalid(forms)

    def forms_valid(self, forms):
        prev_data = deepcopy(self.plan.data)
        for question in forms:
            answer = question['answer']
            form = question['form']
            notesform = question['notesform']
            notesform.is_valid()
            notes = notesform.cleaned_data.get('notes', '')
            choice = form.serialize()
            choice['notes'] = notes
            changed_condition = answer.save_choice(choice, self.request.user)
            if changed_condition:
                self.__LOG.debug('form_valid: q%s/p%s: change saved',
                                 answer.question_id, self.object.pk)
            else:
                self.__LOG.debug('form_valid: q%s/p%s: condition not changed',
                                 answer.question_id, self.object.pk)
        if prev_data != self.plan.data:
            self.plan.modified_by = self.request.user
            self.plan.save(user=self.request.user)
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, forms):
        return self.render_to_response(self.get_context_data(forms=forms))

    def get_form_kwargs(self):
        kwargs = {}
        if self.request.method in ('POST', 'PUT'):
            kwargs['data'] = self.request.POST
        return kwargs

    def get_initial_for_answer(self, answer):
        choice = answer.get_initial(self.plan.data)
        if not choice:
            choice = answer.get_initial(self.plan.previous_data)
        return choice

    def get_forms(self):
        form_kwargs = self.get_form_kwargs()
        form_kwargs.pop('prefix', None)
        forms = []
        for answer in self.answers:
            prefix = 'q{}'.format(answer.question_id)
            initial = self.get_initial_for_answer(answer)
            form = answer.get_form(initial=initial, **form_kwargs)
            notesform = NotesForm(initial=initial, prefix=prefix, **form_kwargs)
            forms.append({
                'form': form,
                'notesform': notesform,
                'answer': answer,
            })
        return forms

    def get_context_data(self, **kwargs):
        context = {}
        context.update(**super().get_context_data(**kwargs))
        context['section'] = self.section
        context['prev_section'] = self.prev_section
        context['next_section'] = self.next_section
        context['section_progress'] = get_section_progress(self.plan, self.section)
        context['forms'] = self.get_forms()
        return context

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


class AbstractQuestionMixin(PlanAccessViewMixin):

    def preload(self, **kwargs):
        """Store frequently used values as early as possible

        Prevents multiple database-queries to fetch known data.
        """
        self.plan_pk = self.kwargs.get('plan')
        plans = (Plan.objects
            .select_related('template')
            .prefetch_related('template__sections'))
        try:
            self.plan = plans.get(id=self.plan_pk)
        except Plan.DoesNotExist:
            raise Http404(f'Plan {self.plan_pk} does not exist. Invalid id?')
        self.template = self.plan.template

    def dispatch(self, request, *args, **kwargs):
        self.preload(**kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_question_pk(self):
        return self.question_pk

    def get_question(self):
        return self.question

    def _get_question(self):
        question_pk = self.question_pk
        # Ensure that the template does contain the question
        try:
            sections = self.template.sections.all()
            question = (Question.objects
                .select_related('section')
                .get(pk=question_pk, section__in=sections)
            )
        except Question.DoesNotExist as e:
            raise Http404(f"Unknown question id: {question_pk}")
        question = question.get_instance()
        return question

    def get_plan_pk(self):
        return self.plan_pk

    def get_plan(self):
        return self.plan

    def get_template(self):
        return self.template


class NewQuestionView(AbstractQuestionMixin, UpdateView):
    "Answer a Question"

    model = Plan
    template_name = 'easydmp/plan/state_form.html'
    pk_url_kwarg = 'plan'
    fields = ('plan_name', 'data')
    __LOG = logging.getLogger('{}.{}'.format(__name__, 'NewQuestionView'))

    def get_queryset(self):
        qs = super().get_queryset().editable(self.request.user)
        return qs.filter(pk=self.get_plan_pk())

    def preload(self, **kwargs):
        super().preload(**kwargs)

        self.queryset = self.get_queryset()

        self.question_pk = self.kwargs.get('question')
        self.question = self._get_question()
        self.answer = AnswerHelper(self.question, self.plan)
        self.section = self.question.section

    def set_referer(self, request):
        self.referer = request.META.get('HTTP_REFERER', None)

    def get_initial(self):
        initial = self.answer.get_initial(self.object.data)
        if not initial:
            initial = self.answer.get_initial(self.object.previous_data)
        return initial

    def get_success_url(self):
        question = self.question
        current_data = self.object.data
        kwargs = {'plan': self.object.pk}

        if 'summary' in self.request.POST:
            LOG.debug('NewQuestionView: Going to summary')
            return reverse('plan_detail', kwargs=kwargs)
        elif 'prev' in self.request.POST:
            prev_question = question.get_prev_question(self.object.data)
            LOG.debug('NewQuestionView: Prev question found: "%s"', prev_question)
            kwargs['question'] = prev_question.pk
        elif 'next' in self.request.POST:
            next_question = question.get_next_question(current_data)
            LOG.debug('NewQuestionView: Next question found: "%s"', next_question)
            if not next_question:
                # Finished answering all questions
                LOG.debug('NewQuestionView: No next question, going to summary')
                return reverse('plan_detail', kwargs=kwargs)
            kwargs['question'] = next_question.pk
        else:
            kwargs['question'] = question.pk

        # Go to next on 'next', prev on 'prev', stay on same page otherwise
        LOG.debug('NewQuestionView: Going to question "%s"', kwargs['question'])
        return reverse('new_question', kwargs=kwargs)

    def get_context_data(self, **kwargs):
        template = self.template
        question = self.question
        section = self.section
        path = section.questions.order_by('position')
        kwargs['path'] = path
        kwargs['question'] = question
        kwargs['question_pk'] = question.pk
        kwargs['notesform'] = kwargs.get('notesform', self.get_notesform())
        kwargs['label'] = question.label
        kwargs['answers'] = question.canned_answers.order().values()
        kwargs['framing_text'] = question.framing_text
        kwargs['section'] = section
        neighboring_questions = Question.objects.filter(section=section)
        kwargs['questions_in_section'] = neighboring_questions
        num_questions = neighboring_questions.count()
        num_questions_so_far = len(question.get_all_preceding_questions())
        kwargs['progress'] = progress(num_questions_so_far, num_questions)
        kwargs['referrer'] = self.referer  # Not a typo! From the http header
        kwargs['section_progress'] = get_section_progress(self.object, section)
        return super().get_context_data(**kwargs)

    def get_notesform(self, **_):
        form_kwargs = self.get_form_kwargs().copy()
        form_kwargs['prefix'] = 'q{}'.format(self.question.pk)
        question = self.question
        form = NotesForm(**form_kwargs)
        return form

    def get_form(self, **_):
        form_kwargs = self.get_form_kwargs()
        question = self.question
        generate_kwargs = {
            'has_prevquestion': question.has_prev_question(),
        }
        generate_kwargs.update(form_kwargs)
        form = make_form(question, **generate_kwargs)
        return form

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.set_referer(request)
        self.__LOG.debug('GET-ing q%s/p%s', self.question_pk, self.object.pk)
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.object,
                  object=self.question, template=template)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.set_referer(request)
        self.__LOG.debug('POST-ing q%s/p%s', self.question_pk, self.object.pk)
        form = self.get_form()
        notesform = self.get_notesform()
        if form.is_valid() and notesform.is_valid():
            self.request = request
            return self.form_valid(form, notesform)
        else:
            return self.form_invalid(form, notesform)

    def form_valid(self, form, notesform):
        self.__LOG.debug('form_valid: q%s/p%s: valid', self.question_pk, self.object.pk)
        notes = notesform.cleaned_data.get('notes', '')
        choice = form.serialize()
        choice['notes'] = notes
        changed_condition = self.answer.save_choice(choice, self.request.user)
        self.object = self.get_object()  # Refresh
        if changed_condition:
            self.__LOG.debug('form_valid: q%s/p%s: change saved',
                             self.question_pk, self.object.pk)
            if self.question.branching_possible:
                self.__LOG.debug('form_valid: q%s/p%s: checking for unreachable answers',
                                 self.question_pk, self.object.pk)
                changed = self.object.hide_unreachable_answers_after(self.question)
                if changed:
                    self.object.quiet_save()
        else:
            self.__LOG.debug('form_valid: q%s/p%s: condition not changed', self.question.pk, self.object.pk)
        template = '{timestamp} {actor} updated {action_object} of {target}'
        log_event(self.request.user, 'update', target=self.object,
                  object=self.question, template=template)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, notesform):
        self.__LOG.debug('q%s/p%s: INvalid', self.question_pk, self.object.pk)
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
            'new_question',
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
        qs = super().get_queryset()
        if self.has_superpowers():
            qs = qs.all()
        else:
            qs = qs.viewable(self.request.user, superpowers=False)
        return qs.order_by('-added')

    def get(self, request, *args, **kwargs):
        next = super().get(request, *args, **kwargs)
        template = '{timestamp} {actor} listed plans'
        log_event(request.user, 'list plan', template=template)
        return next


class PlanDetailView(AbstractQuestionMixin, DetailView):
    "Show an overview of a plan"
    model = Plan
    pk_url_kwarg = 'plan'
    template_name = 'easydmp/plan/plan_detail.html'

    def get_context_data(self, **kwargs):
        context = {
            'output': self.object.get_summary(),
            'plan': self.object,
            'template': self.object.template,
        }
        context.update(**kwargs)
        return super().get_context_data(**context)

    def get(self, request, *args, **kwargs):
        next = super().get(request, *args, **kwargs)
        template = '{timestamp} {actor} accessed {target}'
        log_event(request.user, 'access', target=self.object,
                  template=template)
        return next


def generate_pretty_exported_plan(plan, template_name):
    editors = [access.user for access in
               PlanAccess.objects.filter(plan=plan).filter(may_edit=True)]

    context = plan.get_context_for_generated_text()
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
        qs = self.model.objects.exclude(published=None)
        if self.request.user.is_authenticated:
            qs = qs | self.model.objects.viewable(self.request.user)
        return qs.distinct()

    def generate_exported_plan(self):
        self.object = self.get_object()
        template = self.get_template_names()[0]
        self.export = generate_pretty_exported_plan(self.object, template)

    def log(self, request):
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


class SectionDetailView(DetailView):
    """Show a section

    Mostly relevant for sections without questions.
    """

    model = Section
    pk_url_kwarg = 'section'
    template_name = 'easydmp/plan/section_detail.html'

    def get_plan(self, *args, **kwargs):
        user = self.request.user
        plan_id = kwargs['plan']
        try:
            plan = Plan.objects.viewable(user).get(id=plan_id)
        except Plan.DoesNotExist:
            raise Http404
        return plan

    @staticmethod
    def check_plan(plan, section):
        if plan.template != section.template:
            return False
        return True

    def get_section(self, *args, **kwargs):
        section_id = kwargs['section']
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise Http404
        if not self.check_plan(self.plan, section):
            raise Http404
        return section

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        correct_plan = self.check_plan(self.plan, obj)
        if correct_plan:
            return obj
        raise Http404

    def get(self, request, *args, **kwargs):
        self.plan = self.get_plan(**self.kwargs)
        self.editable = self.plan.may_edit(self.request.user)
        section = self.get_section(**self.kwargs)

        # Set visited empty section
        self.plan.visited_sections.add(section)
        topmost = section.get_topmost_section()
        if topmost:
            self.plan.visited_sections.add(topmost)

        question = section.first_question
        template = '{timestamp} {actor} accessed {action_object} of {target}'
        log_event(request.user, 'access', target=self.plan,
                  object=section, template=template)
        if not question:
            # Show page for empty section
            return super().get(request, *args, **kwargs)

        # Redirect to first question if any
        if self.editable:
            return redirect(
                'new_question',
                question=question.pk,
                plan=self.plan.pk
            )

        return redirect('plan_detail', kwargs={'plan': self.plan.pk})

    def next(self):
        "Generate link to next page"
        plan_pk = self.plan.pk
        next_section = self.object.get_next_section()
        if next_section is not None:
            if self.editable:
                question = next_section.first_question
                # Has questions
                if question:
                    return reverse(
                        'new_question',
                        kwargs={'question': question.pk, 'plan': plan_pk }
                    )
                # Empty section
                return reverse(
                    'section_detail',
                    kwargs={'plan': plan_pk, 'section': next_section.pk}
                )
        return reverse('plan_detail', kwargs={'plan': plan_pk})

    def prev(self):
        "Generate link to previous page"
        plan_pk = self.plan.pk
        prev_section = self.object.get_prev_section()
        if prev_section is not None:
            if self.editable:
                question = prev_section.first_question
                # Has questions
                if question:
                    return reverse(
                        'new_question',
                        kwargs={'question': question.pk, 'plan': plan_pk }
                    )
                # Empty section
                return reverse(
                    'section_detail',
                    kwargs={'plan': plan_pk, 'section': prev_section.pk}
                )
        return reverse('plan_detail', kwargs={'plan': plan_pk})

    def get_context_data(self, **kwargs):
        context = {
            'plan': self.plan,
            'next': self.next(),
            'prev': self.prev(),
            'section_progress': get_section_progress(self.plan, self.object),
        }
        context.update(**kwargs)
        return super().get_context_data(**context)
