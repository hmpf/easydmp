from collections import OrderedDict

from rest_framework import routers


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
