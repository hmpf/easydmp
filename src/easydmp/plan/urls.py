from django.urls import path
from django.views.generic import RedirectView

from .views import (
    ChooseTemplateForNewPlanView,
    StartPlanView,
    UpdatePlanView,
    DeletePlanView,
    SaveAsPlanView,
    AnswerQuestionView,
    FirstQuestionView,
    PlanListView,
    PlanDetailView,
    ValidatePlanView,
    LockPlanView,
    PublishPlanView,
    CreateNewVersionPlanView,
    AnswerLinearSectionView,
    SectionDetailView,
    GeneratedPlanPlainTextView,
    GeneratedPlanHTMLView,
    GeneratedPlanPDFView,
    RedirectToAnswerQuestionView,
)
from .views.access import (
    PlanAccessView,
    UpdatePlanAccessView,
    DeletePlanAccessView,
)


urlpatterns = [
    path('', PlanListView.as_view(), name='plan_list'),
    path('start/', ChooseTemplateForNewPlanView.as_view(), name='choose_template'),
    path('template/<int:template_id>/', StartPlanView.as_view(), name='create_plan'),
    path('new/', RedirectView.as_view(url='/plan/start/'), name='new_plan'),

    path('access/<int:access>/update/', UpdatePlanAccessView.as_view(), name='update_planaccess'),
    path('access/<int:access>/delete/', DeletePlanAccessView.as_view(), name='leave_plan'),
    path('<int:plan>/share/', PlanAccessView.as_view(), name='share_plan'),

    path('<int:plan>/section/<int:section>:<int:answerset>/update/', AnswerLinearSectionView.as_view(), name='answer_linear_section'),
    path('<int:plan>/section/<int:section>/', SectionDetailView.as_view(), name='section_detail'),
    path('<int:plan>/question/<int:question>:<int:answerset>/update/', AnswerQuestionView.as_view(), name='answer_question'),
    path('<int:plan>/<int:question>/new/', RedirectToAnswerQuestionView.as_view(), name='redirect_to_answer_question'),
    path('<int:plan>/update/', UpdatePlanView.as_view(), name='update_plan'),
    path('<int:plan>/check/', ValidatePlanView.as_view(), name='validate_plan'),
    path('<int:plan>/lock/', LockPlanView.as_view(), name='lock_plan'),
    path('<int:plan>/publish/', PublishPlanView.as_view(), name='publish_plan'),
    path('<int:plan>/unlock/', CreateNewVersionPlanView.as_view(), name='unlock_plan'),
    path('<int:plan>/first/new/', FirstQuestionView.as_view(), name='first_question'),
    path('<int:plan>/', PlanDetailView.as_view(), name='plan_detail'),
    path('<int:plan>/delete/', DeletePlanView.as_view(), name='plan_delete'),
    path('<int:plan>/save-as/', SaveAsPlanView.as_view(), name='plan_saveas'),
    path('<int:plan>/generated.txt', GeneratedPlanPlainTextView.as_view(), name='generated_plan_text'),
    path('<int:plan>/generated.html', GeneratedPlanHTMLView.as_view(), name='generated_plan_html'),
    path('<int:plan>/generated.pdf', GeneratedPlanPDFView.as_view(), name='generated_plan_pdf'),
]
