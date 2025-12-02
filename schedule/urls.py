from django.urls import path
from . import views

urlpatterns = [
    path('', views.monthly_schedule, name='monthly_schedule'),
    path('save/', views.save_monthly_schedule, name='save_monthly_schedule'),
]