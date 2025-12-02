# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # http://127.0.0.1:8000/ 접속 시 dashboard 뷰 실행
    path('', views.dashboard, name='dashboard'),
]