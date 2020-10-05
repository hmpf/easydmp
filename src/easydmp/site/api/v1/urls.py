from collections import OrderedDict

from django.conf.urls import url, include

from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.views import refresh_jwt_token
from rest_framework_jwt.views import verify_jwt_token

from easydmp.auth.api.v1 import router as auth_router
from easydmp.auth.api.v1.views import authorize_jwt_token
from easydmp.dmpt.api.v1 import router as dmpt_router
from easydmp.lib.api.routers import ContainerRouter
from easydmp.plan.api.v1 import router as plan_router


jwt_urls = [
    url(r'jwt/authenticate/$', obtain_jwt_token, name='obtain_jwt_token',),
    url(r'jwt/refresh/$', refresh_jwt_token, name='refresh_jwt_token'),
    url(r'jwt/verify/$', verify_jwt_token, name='verify_jwt_token'),
    url(r'jwt/authorize/$', authorize_jwt_token, name='authorize_jwt_token'),
]

router = ContainerRouter()
router.prepend_urls(jwt_urls)
router.register_router(plan_router)
router.register_router(auth_router)
router.register_router(dmpt_router)

urlpatterns = jwt_urls + [
    url(r'auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^', include(router.urls)),
]

app_name = 'v1'
