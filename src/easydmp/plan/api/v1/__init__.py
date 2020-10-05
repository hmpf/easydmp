from rest_framework.routers import DefaultRouter

from .views import PlanViewSet


router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
