"""easydmp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.urls import path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from easydmp.site.views import Homepage
from easydmp.site.views import LoginView
from easydmp.site.views import logout_view
from easydmp.site.views import PublicTemplateView

urlpatterns = [
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),

    url('^psa/', include('social_django.urls', namespace='social')),
    url(r'^select2/', include('django_select2.urls')),

    url('^$', Homepage.as_view(), name='home'),
    url('^login/', LoginView.as_view(), name='login-selector'),
    url('^logout', logout_view, name='logout'),
    url('^privacy/', PublicTemplateView.as_view(template_name='privacy.html'), name='privacy'),
    url('^account/', include('easydmp.auth.urls')),

    url(r'^plan/', include('easydmp.plan.urls')),
    url(r'^invitation/', include('easydmp.invitation.urls')),

    url(r'dmpt/', include('easydmp.dmpt.urls')),

    path('api/', RedirectView.as_view(pattern_name='swagger-ui'), name='go-to-swagger-ui'),
    path('api/schema/',SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    url(r'^api/v1/', include('easydmp.site.api.urls', namespace='v1')),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
