from django.urls import path

from . import views


urlpatterns = [
    path('missing-info/<backend>/', views.GetFullnameView.as_view(), name='missing-info'),
]
