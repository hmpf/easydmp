from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r'templates', views.TemplateViewSet)
router.register(r'template-import-metadata', views.TemplateImportMetadataViewSet)
router.register(r'sections', views.SectionViewSet)
router.register(r'questions', views.QuestionViewSet, basename='question')
router.register(r'canned-answers', views.CannedAnswerViewSet)
router.register(r'explicitbranches', views.ExplicitBranchViewSet, basename='explicitbranch')
