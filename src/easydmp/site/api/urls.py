from collections import OrderedDict

from django.conf.urls import url, include

from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.views import refresh_jwt_token
from rest_framework_jwt.views import verify_jwt_token

from easydmp.auth.api.views import authorize_jwt_token
from easydmp.plan.api import router as plan_router
from easydmp.auth.api import router as auth_router
from easydmp.dmpt.api import router as dmpt_router
from flow.api import router as flow_router


class ContainerRouter(routers.DefaultRouter):
    prepended_urls = ()
    appended_urls = ()

    def register_router(self, router):
        self.registry.extend(router.registry)

    def prepend_urls(self, args):
        args = list(args)
        if self.prepended_urls:
            self.prepended_urls += args
        else:
            self.prepended_urls = args or []

    def append_urls(self, args):
        args = list(args)
        if self.appended_urls:
            self.appended_urls += args
        else:
            self.appended_urls = args or []

    def get_api_root_view(self, api_urls=None):
        api_root_dict = OrderedDict()
        for urlobj in self.prepended_urls:
            api_root_dict[urlobj.name] = urlobj.name

        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        for urlobj in self.appended_urls:
            api_root_dict[urlobj.name] = urlobj.name

        return self.APIRootView.as_view(api_root_dict=api_root_dict)

    def get_urls(self):
        urls = super().get_urls()
        urls = list(self.prepended_urls) + urls + list(self.appended_urls)
        return urls


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
router.register_router(flow_router)

urlpatterns = jwt_urls + [
    url(r'auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^', include(router.urls)),
]
