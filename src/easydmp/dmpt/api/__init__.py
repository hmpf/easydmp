from rest_framework.routers import DefaultRouter

from . import views
from .views import TemplateViewSet
from .views import SectionViewSet
from .views import QuestionViewSet
from .views import CannedAnswerViewSet
from .views import ExplicitBranchViewSet


router = DefaultRouter()
router.register(r'templates', views.TemplateViewSet)
router.register(r'sections', views.SectionViewSet)
router.register(r'questions', views.QuestionViewSet, basename='question')
router.register(r'canned-answers', views.CannedAnswerViewSet)
router.register(r'explicitbranches', views.ExplicitBranchViewSet, basename='explicitbranch')
