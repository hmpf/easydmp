from rest_framework.routers import DefaultRouter

from .views import PlanViewSet
from .views import AnswerSetViewSet
from .views import AnswerViewSet


router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'answersets', AnswerSetViewSet, basename='answerset')
router.register(r'answers', AnswerViewSet, basename='answer')
