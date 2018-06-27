from django.conf.urls import url, include

from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.views import refresh_jwt_token
from rest_framework_jwt.views import verify_jwt_token

from easydmp.plan.api import router as plan_router
from easydmp.auth.api import router as auth_router
from easydmp.dmpt.api import router as dmpt_router
from flow.api import router as flow_router


class ContainerRouter(routers.DefaultRouter):
    def register_router(self, router):
        self.registry.extend(router.registry)


router = ContainerRouter()
router.register_router(plan_router)
router.register_router(auth_router)
router.register_router(dmpt_router)
router.register_router(flow_router)

#assert False, router.urls

urlpatterns = [
    url(r'jwt/authenticate/$', obtain_jwt_token),
    url(r'jwt/refresh/$', refresh_jwt_token),
    url(r'jwt/verify/$', verify_jwt_token),
    url(r'auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^', include(router.urls)),
]
