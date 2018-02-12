from django.conf.urls import url

from .views import (
    NewPlanView,
    UpdatePlanView,
    DeletePlanView,
    NewQuestionView,
    FirstQuestionView,
    PlanListView,
    PlanDetailView,
    SectionDetailView,
    GeneratedPlanPlainTextView,
    GeneratedPlanHTMLView,
    GeneratedPlanPDFView,
)


PLAN_RE = r'(?P<plan>\d+)'
PLAN_PAGEROOT_RE = r'%s/' % PLAN_RE
SECTION_RE = r'(?P<section>\d+)'
SECTION_PAGEROOT_RE = r'%s/section/%s/' % (PLAN_RE, SECTION_RE)
QUESTION_RE = r'(?P<question>\d+)'
QUESTION_PAGEROOT_RE = r'^%s/%s/' % (PLAN_RE, QUESTION_RE)

urlpatterns = [
    url(r'^$', PlanListView.as_view(), name='plan_list'),
    url(r'^new/$', NewPlanView.as_view(), name='new_plan'),
    url(PLAN_PAGEROOT_RE + 'update/$', UpdatePlanView.as_view(), name='update_plan'),
    url(PLAN_PAGEROOT_RE + 'first/new/$', FirstQuestionView.as_view(), name='first_question'),
    url(QUESTION_PAGEROOT_RE + r'new/$', NewQuestionView.as_view(), name='new_question'),
    url(SECTION_PAGEROOT_RE + r'$', SectionDetailView.as_view(), name='section_detail'),
    url(PLAN_PAGEROOT_RE + r'$', PlanDetailView.as_view(), name='plan_detail'),
    url(PLAN_PAGEROOT_RE + r'delete/$', DeletePlanView.as_view(), name='plan_delete'),
    url(PLAN_PAGEROOT_RE + r'generated.txt$', GeneratedPlanPlainTextView.as_view(), name='generated_plan_text'),
    url(PLAN_PAGEROOT_RE + r'generated.html$', GeneratedPlanHTMLView.as_view(), name='generated_plan_html'),
    url(PLAN_PAGEROOT_RE + r'generated.pdf$', GeneratedPlanPDFView.as_view(), name='generated_plan_pdf'),
]
