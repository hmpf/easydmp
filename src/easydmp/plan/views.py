from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse, reverse_lazy
from django.db import IntegrityError
from django.http import HttpResponseRedirect, Http404, HttpResponseServerError
from django.shortcuts import render, redirect
from django.views.generic import (
    FormView,
    CreateView,
    UpdateView,
    DetailView,
    ListView,
    DeleteView,
    RedirectView,
)
from django.utils.html import mark_safe

from easydmp.utils import pprint_list, utc_epoch
from easydmp.dmpt.forms import make_form, TemplateForm, DeleteForm, NotesForm
from easydmp.dmpt.models import Template, Question, Section
from flow.models import FSA

from .models import Plan
from .models import PlanComment
from .forms import NewPlanForm
from .forms import UpdatePlanForm
from .forms import SaveAsPlanForm
from .forms import PlanCommentForm
from .forms import ConfirmForm


def progress(so_far, all):
    "Returns percentage done, as float"
    return so_far/float(all)*100


def has_prevquestion(question, data):
     return bool(question.get_prev_question(data))


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


class DeleteFormMixin(FormView):
    form_class = DeleteForm


class AbstractPlanViewMixin:

    def get_success_url(self):
        kwargs = {
            'plan': self.object.pk,
            'question': self.object.get_first_question().pk,
        }
        return reverse('new_question', kwargs=kwargs)

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
        groups = user.groups.all()
        qs = qs.filter(editor_group__in=groups)
        if not qs:
            return None
        return qs


class NewPlanView(AbstractPlanViewMixin, LoginRequiredMixin, CreateView):
    """Create a new empty plan from the given template

    Chceks that the same adder do not have a plan of the same name already.
    """
    template_name = 'easydmp/plan/newplan_form.html'
    model = Plan
    form_class = NewPlanForm

    def get_success_url(self):
        kwargs = {
            'plan': self.object.pk,
            'question': self.object.get_first_question().pk,
        }
        return reverse('new_question', kwargs=kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.data = {}
        self.object.previous_data = {}
        self.object.added_by = self.request.user
        self.object.modified_by = self.request.user
        self.object.template = form.cleaned_data['template_type']
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


class UpdatePlanView(AbstractPlanViewMixin, LoginRequiredMixin, UpdateView):
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


class DeletePlanView(LoginRequiredMixin, DeleteFormMixin, DeleteView):
    model = Plan
    template_name = 'easydmp/plan/plan_confirm_delete.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(added_by=self.request.user)

    def delete(self, request, *args, **kwargs):
        if 'cancel' in request.POST:
            return HttpResponseRedirect(self.get_success_url())
        return super().delete(request, *args, **kwargs)


class SaveAsPlanView(LoginRequiredMixin, UpdateView):
    model = Plan
    template_name = 'easydmp/plan/plan_confirm_save_as.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'plan'
    form_class = SaveAsPlanForm

    def get_queryset(self):
        qs = super().get_queryset().select_related('editor_group')
        user_groups = self.request.user.groups.all()
        return qs.filter(editor_group__in=user_groups)

    def form_valid(self, form):
        title = form.cleaned_data['title']
        abbreviation = form.cleaned_data.get('abbreviation', '')
        keep_editors = form.cleaned_data.get('keep_editors', True)
        self.object.save_as(title, self.request.user, abbreviation, keep_editors)
        return HttpResponseRedirect(self.get_success_url())


class ValidatePlanView(LoginRequiredMixin, UpdateView):
    template_name = 'easydmp/plan/plan_confirm_validate.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().filter(valid=False)
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.validate()
        return HttpResponseRedirect(success_url)


class LockPlanView(LoginRequiredMixin, UpdateView):
    template_name = 'easydmp/plan/plan_confirm_lock.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().filter(locked__isnull=True)
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.lock(request.user)
        return HttpResponseRedirect(success_url)


class PublishPlanView(LoginRequiredMixin, UpdateView):
    template_name = 'easydmp/plan/plan_confirm_publish.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().filter(valid=True)
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.publish(request.user)
        return HttpResponseRedirect(success_url)


class CreateNewVersionPlanView(LoginRequiredMixin, UpdateView):
    template_name = 'easydmp/plan/plan_confirm_createnewversion.html'
    form_class = ConfirmForm
    model = Plan
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset().filter(locked__isnull=False)
        return qs

    def get_success_url(self):
        return reverse('plan_detail', kwargs={'plan': self.object.pk})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.create_new_version(request.user)
        return HttpResponseRedirect(success_url)


class AbstractQuestionMixin:

    def get_question_pk(self):
        question_pk = self.kwargs.get('question')
        return question_pk

    def get_question(self):
        question_pk = self.get_question_pk()
        try:
            sections = Section.objects.filter(template=self.get_template())
            question = Question.objects.get(pk=question_pk, section__in=sections)
        except Question.DoesNotExist as e:
            raise ValueError("Unknown question id: {}".format(question_pk))
        question = question.get_instance()
        return question

    def get_plan_pk(self):
        return self.kwargs.get('plan')

    def get_queryset(self):
        return self.model.objects.filter(pk=self.get_plan_pk())

    def get_plan(self):
        plan_id = self.get_plan_pk()
        return Plan.objects.get(id=plan_id)

    def get_template(self):
        plan = self.get_plan()
        return plan.template


class AbstractQuestionView(LoginRequiredMixin, AbstractQuestionMixin, UpdateView):
    model = Plan
    template_name = 'easydmp/plan/state_form.html'
    pk_url_kwarg = 'plan'
    fields = ('plan_name', 'data')


class NewQuestionView(AbstractQuestionView):

    def set_referer(self, request):
        self.referer = request.META.get('HTTP_REFERER', None)

    def get_initial(self):
        current_data = self.object.data or {}
        previous_data = self.object.previous_data or {}
        question_pk = str(self.get_question().pk)
        initial = current_data.get(question_pk, {})
        if not initial:
            initial = previous_data.get(question_pk, {})
        return initial

    def get_success_url(self):
        question = self.get_question()
        current_data = self.object.data
        kwargs = {'plan': self.object.pk}

        if 'summary' in self.request.POST:
            return reverse('plan_detail', kwargs=kwargs)
        elif 'prev' in self.request.POST:
            prev_question = question.get_prev_question(self.object.data)
            kwargs['question'] = prev_question.pk
        elif 'next' in self.request.POST:
            next_question = question.get_next_question(current_data)
            if not next_question:
                # Finished answering all questions
                return reverse('plan_detail', kwargs=kwargs)
            kwargs['question'] = next_question.pk
        else:
            kwargs['question'] = question.pk

        # Go to next on 'next', prev on 'prev', stay on same page otherwise
        return reverse('new_question', kwargs=kwargs)

    def get_context_data(self, **kwargs):
        template = self.get_template()
        question = self.get_question()
        section = question.section
        path = section.find_path(self.object.data)
        kwargs['path'] = path
        kwargs['question'] = question
        kwargs['question_pk'] = question.pk
        kwargs['notesform'] = kwargs.get('notesform', self.get_notesform())
        kwargs['commentform'] = kwargs.get('commentform', self.get_commentform())
        kwargs['label'] = question.label
        kwargs['answers'] = question.canned_answers.values()
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
        form_kwargs = self.get_form_kwargs()
        question = self.get_question()
        form = NotesForm(**form_kwargs)
        return form

    def get_form(self, **_):
        form_kwargs = self.get_form_kwargs()
        question = self.get_question()
        generate_kwargs = {
            'has_prevquestion': has_prevquestion(question, self.object.data),
        }
        generate_kwargs.update(form_kwargs)
        form = make_form(question, **generate_kwargs)
        return form

    def get_commentform(self, **_):
        form_kwargs = self.get_form_kwargs()
        form = PlanCommentForm(**form_kwargs)
        return form

    def delete_statedata(self, *args):
        """Delete data for the statenames in args"""
        for statename in args:
            self.object.data.pop(statename, None)
        self.object.save()

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.set_referer(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.set_referer(request)
        form = self.get_form()
        notesform = self.get_notesform()
        if form.is_valid() and notesform.is_valid():
            self.request = request
            return self.form_valid(form, notesform)
        else:
            return self.form_invalid(form, notesform)

    def form_valid(self, form, notesform):
        notes = notesform.cleaned_data.get('notes', '')
        choice = form.serialize()
        choice['notes'] = notes
        question_pk = self.get_question_pk()
        # save change
        current_data = self.object.data
        current_data[question_pk] = choice
        self.object.data = current_data
        previous_data = self.object.previous_data
        previous_data[question_pk] = choice
        self.object.previous_data = previous_data
        self.object.save(question=self.get_question())
        # remove invalidated states
#         paths_from = self.get_template().find_paths_from(question_pk)
#         invalidated_states = set(chain(*paths_from))
#         invalidated_states.discard(None)
#         invalidated_states.discard(question_pk)
#         self.delete_statedata(*invalidated_states)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, notesform):
        return self.render_to_response(
            self.get_context_data(form=form, notesform=notesform))


class FirstQuestionView(LoginRequiredMixin, RedirectView):

    def get_redirect_url(self, *args, **kwargs):
        plan_pk = self.kwargs.get('plan')
        plan = Plan.objects.get(pk=plan_pk)
        question_pk = plan.get_first_question().pk
        url = reverse(
            'new_question',
            kwargs={'plan': plan_pk, 'question': question_pk}
        )
        return url


class AddCommentView(LoginRequiredMixin, AbstractQuestionMixin, CreateView):
    model = PlanComment
    form_class = PlanCommentForm

    def get_success_url(self):
        question_pk = self.get_question_pk()
        plan_pk = self.get_plan_pk()
        kwargs = {'plan': plan_pk, 'question': question_pk}
        return reverse('new_question', kwargs=kwargs)

    def form_valid(self, form):
        comment = form.cleaned_data.get('comment', '')
        question_pk = self.get_question_pk()
        plan_pk = self.get_plan_pk()
        PlanComment.objects.create(plan_id=plan_pk, question_id=question_pk,
                                   comment=comment, added_by=self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = 'easydmp/plan/plan_list.html'

    def get_queryset(self):
        groups = self.request.user.groups.all()
        return self.model.objects.filter(editor_group__in=groups).order_by('-added')


class AbstractPlanDetailView(LoginRequiredMixin, AbstractQuestionMixin, DetailView):
    model = Plan
    pk_url_kwarg = 'plan'

    def get_context_data(self, **kwargs):
        context = self.object.get_context_for_generated_text()
        context.update(**kwargs)
        return super().get_context_data(**context)


class PlanDetailView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/plan_detail.html'


class GeneratedPlanHTMLView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.html'


class GeneratedPlanPlainTextView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.txt'
    content_type = 'text/plain; charset=UTF-8'


class GeneratedPlanPDFView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.pdf'
    content_type = 'text/plain'


class SectionDetailView(DetailView):
    model = Section
    pk_url_kwarg = 'section'
    template_name = 'easydmp/plan/section_detail.html'

    def get_plan(self, *args, **kwargs):
        plan_id = kwargs['plan']
        try:
            plan = Plan.objects.get(id=plan_id)
        except Section.DoesNotExist:
            raise Http404
        return plan

    def check_plan(self, plan, section):
        if plan.template != section.template:
            return False
        return True

    def get_section(self, *args, **kwargs):
        section_id = kwargs['section']
        plan = self.get_plan(*args, **kwargs)
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            raise Http404
        if not self.check_plan(plan, section):
            raise Http404
        return section

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        plan = self.get_plan(**self.kwargs)
        correct_plan = self.check_plan(plan, obj)
        if correct_plan:
            return obj
        raise Http404

    def dispatch(self, *args, **kwargs):
        section = self.get_section(**self.kwargs)
        plan = self.get_plan(**self.kwargs)

        # Set visited empty section
        plan.visited_sections.add(section)
        topmost = section.get_topmost_section()
        if topmost:
            plan.visited_sections.add(topmost)

        # Redirect to first question if any
        question = section.get_first_question()
        if question:
            return redirect('new_question', question=question.pk, plan=plan.pk)

        # Show page for empty section
        return super().dispatch(*args, **kwargs)

    def next(self):
        "Generate link to next page"
        plan = self.get_plan(**self.kwargs)
        next_section = self.object.get_next_section()
        if next_section is not None:
            question = next_section.get_first_question()
            if question:
                return reverse('new_question', kwargs={'question': question.pk,
                                                   'plan': plan.pk })
            return reverse('section_detail', kwargs={'plan': plan.pk,
                                                     'section':
                                                     next_section.pk})
        return reverse('plan_detail', kwargs={'plan': plan.pk})

    def prev(self):
        "Generate link to previous page"
        plan = self.get_plan(**self.kwargs)
        prev_section = self.object.get_prev_section()
        if prev_section is not None:
            question = prev_section.get_first_question()
            if question:
                return reverse('new_question', kwargs={'question': question.pk,
                                                   'plan': plan.pk })
            return reverse('section_detail', kwargs={'plan': plan.pk,
                                                     'section':
                                                     prev_section.pk})
        return reverse('plan_detail', kwargs={'plan': plan.pk})

    def get_context_data(self, **kwargs):
        plan = self.get_plan(**self.kwargs)
        next = self.object.get_next_section()
        prev = self.object.get_prev_section()
        context = {
            'plan': plan,
            'next': self.next(),
            'prev': self.prev(),
            'section_progress': get_section_progress(plan, self.object),
        }
        context.update(**kwargs)
        return super().get_context_data(**context)
