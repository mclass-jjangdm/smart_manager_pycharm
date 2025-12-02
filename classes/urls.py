# classes/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.class_list, name='class_list'),
    path('new/', views.class_create, name='class_create'),
    path('<int:pk>/edit/', views.class_update, name='class_update'),
    path('<int:pk>/delete/', views.class_delete, name='class_delete'),

    # 수강생 관리용 URL
    path('student/<int:student_pk>/drop/<int:class_pk>/', views.student_class_drop, name='student_class_drop'),
    path('student/<int:student_pk>/charge/<int:class_pk>/', views.tuition_charge, name='tuition_charge'),
    path('tuition/<int:log_pk>/settle/', views.tuition_settle, name='tuition_settle'),

    # 일괄 청구 URL
    path('batch-charge/', views.monthly_batch_charge, name='monthly_batch_charge'),
]