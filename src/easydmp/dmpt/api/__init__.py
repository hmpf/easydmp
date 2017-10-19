from rest_framework.routers import DefaultRouter

from .views import TemplateViewSet
from .views import SectionViewSet
from .views import QuestionViewSet
from .views import CannedAnswerViewSet


router = DefaultRouter()
router.register(r'templates', TemplateViewSet)
router.register(r'sections', SectionViewSet)
router.register(r'questions', QuestionViewSet)
router.register(r'canned-answers', CannedAnswerViewSet)
