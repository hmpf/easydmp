from rest_framework.routers import DefaultRouter

from . import views
from .views import TemplateViewSet
from .views import SectionViewSet
from .views import QuestionViewSet
from .views import CannedAnswerViewSet


router = DefaultRouter()
router.register(r'templates', views.TemplateViewSet)
router.register(r'sections', views.SectionViewSet)
router.register(r'questions', views.QuestionViewSet, base_name='question')
router.register(r'canned-answers', views.CannedAnswerViewSet)
