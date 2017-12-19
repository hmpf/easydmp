from collections import OrderedDict
from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse, reverse_lazy
from django.db import IntegrityError
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.views.generic import (
    FormView,
    CreateView,
    UpdateView,
    DetailView,
    ListView,
    DeleteView,
    RedirectView,
)

from easydmp.utils import pprint_list, utc_epoch
from easydmp.dmpt.forms import make_form, TemplateForm, DeleteForm, NotesForm
from easydmp.dmpt.models import Template, Question, Section
from flow.models import FSA

from .models import Plan
from .forms import PlanForm


def progress(so_far, all):
    "Returns percentage done, as float"
    return so_far/float(all)*100


def has_prevquestion(question, data):
     return bool(question.get_prev_question(data))


class DeleteFormMixin(FormView):
    form_class = DeleteForm


class NewPlanView(LoginRequiredMixin, CreateView):
    """Create a new empty plan from the given template

    Chceks that the same adder do not have a plan of the same name already.
    """
    template_name = 'easydmp/plan/newplan_form.html'
    model = Plan
    form_class = PlanForm

    def get_success_url(self):
        kwargs = {
            'plan': self.object.pk,
            'question': self.object.get_first_question().pk,
        }
        return reverse('new_question', kwargs=kwargs)

    def dedup_title(self):
        qs = self.model.objects.filter(
            added_by=self.request.user,
            template=self.object.template,
            title=self.object.title,
        )
        if qs.exists():
            epoch = utc_epoch()
            self.object.title = '{} {}'.format(self.object.title, epoch)
            return True
        return False

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.data = {}
        self.object.previous_data = {}
        self.object.added_by = self.request.user
        self.object.modified_by = self.request.user
        self.object.template = form.cleaned_data['template_type']
        try:
            self.object.save()
        except IntegrityError:
            deduped = self.dedup_title()
            if deduped:
                messages.warning(self.request, 'You have already created a plan with this title. Title changed to prevent duplicates')
                self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class DeletePlanView(LoginRequiredMixin, DeleteFormMixin, DeleteView):
    model = Plan
    template_name = 'easydmp/plan/plan_confirm_delete.html'
    success_url = reverse_lazy('plan_list')
    pk_url_kwarg = 'plan'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(added_by=self.request.user)


class AbstractQuestionMixin(object):

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

    def get_template(self):
        plan_id = self.get_plan_pk()
        plan = Plan.objects.get(id=plan_id)
        return plan.template


class AbstractQuestionView(LoginRequiredMixin, AbstractQuestionMixin, UpdateView):
    model = Plan
    template_name = 'easydmp/plan/state_form.html'
    pk_url_kwarg = 'plan'
    fields = ('plan_name', 'data')


class NewQuestionView(AbstractQuestionView):

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
        next_question = question.get_next_question(current_data)
        kwargs = {'plan': self.object.pk}
        if next_question:
            kwargs['question'] = next_question.pk
            return reverse('new_question', kwargs=kwargs)
        return reverse('plan_detail', kwargs=kwargs)

    def get_context_data(self, **kwargs):
        template = self.get_template()
        question = self.get_question()
        kwargs['question'] = question
        kwargs['question_pk'] = question.pk
        kwargs['notesform'] = kwargs.get('notesform', self.get_notesform())
        kwargs['label'] = question.label
        kwargs['answers'] = question.canned_answers.values()
        kwargs['framing_text'] = question.framing_text
        section = question.section
        kwargs['section'] = section
        neighboring_questions = Question.objects.filter(section=section)
        kwargs['questions_in_section'] = neighboring_questions
        num_questions = neighboring_questions.count()
        num_questions_so_far = len(question.get_all_prev_questions())
        kwargs['progress'] = progress(num_questions_so_far, num_questions)
        return super().get_context_data(**kwargs)

    def get_notesform(self, **_):
        form_kwargs = self.get_form_kwargs()
        question = self.get_question()
        generate_kwargs = {
            'has_prevquestion': has_prevquestion(question, self.object.data),
        }
        generate_kwargs.update(form_kwargs)
        form = NotesForm(**generate_kwargs)
        return form

    def get_form(self, **_):
        form_kwargs = self.get_form_kwargs()
        question = self.get_question()
        form = make_form(question, **form_kwargs)
        return form

    def delete_statedata(self, *args):
        """Delete data for the statenames in args"""
        for statename in args:
            self.object.data.pop(statename, None)
        self.object.save()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'prev' in request.POST:
            prev_question = self.get_question().get_prev_question(self.object.data)
            kwargs = {
                'question': prev_question.pk,
                'plan': self.object.pk,
            }
            return HttpResponseRedirect(reverse('new_question', kwargs=kwargs))
        form = self.get_form()
        notesform = self.get_notesform()
        if form.is_valid() and notesform.is_valid():
            return self.form_valid(form, notesform)
        else:
            return self.form_invalid(form, notesform)

    def form_valid(self, form, notesform):
        notes = notesform.cleaned_data.get('notes', '')
        state_switch = form.serialize()
        state_switch['notes'] = notes
        question_pk = self.get_question_pk()
        # save change
        current_data = self.object.data
        current_data[question_pk] = state_switch
        self.object.data = current_data
        previous_data = self.object.previous_data
        previous_data[question_pk] = state_switch
        self.object.previous_data = previous_data
        self.object.save()
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


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = 'easydmp/plan/plan_list.html'

    def get_queryset(self):
        groups = self.request.user.groups.all()
        return self.model.objects.filter(editor_group__in=groups).order_by('-added')


class AbstractPlanDetailView(LoginRequiredMixin, AbstractQuestionMixin, DetailView):
    model = Plan
    pk_url_kwarg = 'plan'

    def get_canned_text(self):
        data = self.object.data.copy()
        return self.get_template().generate_canned_text(data)

    def massage_text(self, text):
        return text

    def get_context_data(self, **kwargs):
        kwargs['data'] = self.object.data.copy()
        kwargs['text'] = self.get_canned_text()
        return super().get_context_data(**kwargs)


class PlanDetailView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/plan_detail.html'

    def get_context_data(self, **kwargs):
        kwargs = super().get_context_data(**kwargs)
        outputs = OrderedDict()
        data = kwargs['data']
        template = self.get_template()
        for section in template.sections.all():
            section_output = OrderedDict()
            for question in section.questions.all():
                question = question.get_instance()
                value = data.get(str(question.pk), None)
                if not value or value.get('choice', None) is None:
                    continue
                value['answer'] = question.pprint_html(value)
                value['question'] = question
                section_output[question.pk] = value
            outputs[section.title] = section_output
        #kwargs['output'] = OrderedDict(template.order_data(outputs))
        kwargs['output'] = outputs
        return kwargs


class GeneratedPlanHTMLView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.html'


class GeneratedPlanPlainTextView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.txt'
    content_type = 'text/plain; charset=UTF-8'


class GeneratedPlanPDFView(AbstractPlanDetailView):
    template_name = 'easydmp/plan/generated_plan.pdf'
    content_type = 'text/plain'
