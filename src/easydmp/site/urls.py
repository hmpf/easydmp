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
from django.conf.urls import url, include
from django.contrib import admin

from easydmp.site.views import Homepage, logout_view

urlpatterns = [
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),

    url('^psa/', include('social_django.urls', namespace='social')),

    url('^$', Homepage.as_view(), name='home'),
    url('^logout', logout_view, name='logout'),
    url(r'^plan/', include('easydmp.plan.urls')),
    url(r'^invitation/', include('easydmp.invitation.urls')),

    url(r'dmpt/', include('easydmp.dmpt.urls')),

    url(r'^api/v1/', include('easydmp.site.api.urls', namespace='v1')),
]
