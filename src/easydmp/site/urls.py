"""easydmp URL Configuration"""

from django.conf import settings
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from easydmp.site.views import Homepage
from easydmp.site.views import LoginView
from easydmp.site.views import logout_view
from easydmp.site.views import PublicTemplateView


urlpatterns = [
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),

    path('psa/', include('social_django.urls', namespace='social')),
    path('select2/', include('django_select2.urls')),

    path('', Homepage.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login-selector'),
    path('logout', logout_view, name='logout'),
    path('privacy/', PublicTemplateView.as_view(template_name='privacy.html'), name='privacy'),
    path('account/', include('easydmp.auth.urls')),

    path('plan/', include('easydmp.plan.urls')),
    path('invitation/', include('easydmp.invitation.urls')),

    path('dmpt/', include('easydmp.dmpt.urls')),

    path('api/', RedirectView.as_view(pattern_name='swagger-ui'), name='go-to-swagger-ui'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/', include('easydmp.site.api.v1.urls', namespace='v1')),
    path('api/v2/', include('easydmp.site.api.v2.urls', namespace='v2')),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
