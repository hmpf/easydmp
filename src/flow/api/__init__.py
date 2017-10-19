from rest_framework.routers import DefaultRouter

from .views import NodeViewSet
from .views import EdgeViewSet
from .views import FSAViewSet


router = DefaultRouter()
router.register(r'node', NodeViewSet)
router.register(r'edge', EdgeViewSet)
router.register(r'fsa', FSAViewSet)
