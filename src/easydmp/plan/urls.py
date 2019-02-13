from django.conf.urls import url

from .views import (
    NewPlanView,
    UpdatePlanView,
    DeletePlanView,
    SaveAsPlanView,
    NewQuestionView,
    FirstQuestionView,
    AddCommentView,
    PlanListView,
    PlanDetailView,
    ValidatePlanView,
    LockPlanView,
    PublishPlanView,
    CreateNewVersionPlanView,
    UpdateLinearSectionView,
    SectionDetailView,
    GeneratedPlanPlainTextView,
    GeneratedPlanHTMLView,
    GeneratedPlanPDFView,
)
from .views.access import (
    PlanAccessView,
    UpdatePlanAccessView,
    DeletePlanAccessView,
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

    url(r'access/(?P<access>\d+)/update/$', UpdatePlanAccessView.as_view(), name='update_planaccess'),
    url(r'access/(?P<access>\d+)/delete/$', DeletePlanAccessView.as_view(), name='leave_plan'),
    url(PLAN_PAGEROOT_RE + 'share/$', PlanAccessView.as_view(), name='share_plan'),

    url(SECTION_PAGEROOT_RE + r'update/$', UpdateLinearSectionView.as_view(), name='answer_linear_section'),
    url(SECTION_PAGEROOT_RE + r'$', SectionDetailView.as_view(), name='section_detail'),
    url(PLAN_PAGEROOT_RE + 'update/$', UpdatePlanView.as_view(), name='update_plan'),
    url(PLAN_PAGEROOT_RE + 'check/$', ValidatePlanView.as_view(), name='validate_plan'),
    url(PLAN_PAGEROOT_RE + 'lock/$', LockPlanView.as_view(), name='lock_plan'),
    url(PLAN_PAGEROOT_RE + 'publish/$', PublishPlanView.as_view(), name='publish_plan'),
    url(PLAN_PAGEROOT_RE + 'unlock/$', CreateNewVersionPlanView.as_view(), name='unlock_plan'),
    url(PLAN_PAGEROOT_RE + 'first/new/$', FirstQuestionView.as_view(), name='first_question'),
    url(QUESTION_PAGEROOT_RE + r'new/$', NewQuestionView.as_view(), name='new_question'),
    url(QUESTION_PAGEROOT_RE + r'comment/$', AddCommentView.as_view(), name='new_comment'),
    url(PLAN_PAGEROOT_RE + r'$', PlanDetailView.as_view(), name='plan_detail'),
    url(PLAN_PAGEROOT_RE + r'delete/$', DeletePlanView.as_view(), name='plan_delete'),
    url(PLAN_PAGEROOT_RE + r'save-as/$', SaveAsPlanView.as_view(), name='plan_saveas'),
    url(PLAN_PAGEROOT_RE + r'generated.txt$', GeneratedPlanPlainTextView.as_view(), name='generated_plan_text'),
    url(PLAN_PAGEROOT_RE + r'generated.html$', GeneratedPlanHTMLView.as_view(), name='generated_plan_html'),
    url(PLAN_PAGEROOT_RE + r'generated.pdf$', GeneratedPlanPDFView.as_view(), name='generated_plan_pdf'),
]
