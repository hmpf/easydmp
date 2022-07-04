from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r'rdadcs/keys', views.RDADCSKeyViewSet, basename='rdadcskey')
router.register(r'rdadcs/question-links', views.RDADCSQuestionLinkViewSet, basename='rdadcsquestionlink')
router.register(r'rdadcs/section-links', views.RDADCSSectionLinkViewSet, basename='rdadcssectionlink')
