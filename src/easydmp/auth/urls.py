from django.urls import path

from . import views


urlpatterns = [
    path('missing-info/<backend>/', views.GetFullnameView.as_view(), name='missing-info'),
    path('missing-email/<backend>/', views.GetEmailView.as_view(), name='missing-email'),
]
