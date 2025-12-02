# teachers/urls.py

from django.urls import path, reverse
from . import views

urlpatterns = [
    # 기본 관리
    path('', views.teacher_list, name='teacher_list'),
    path('new/', views.teacher_create, name='teacher_create'),
    path('<int:pk>/edit/', views.teacher_update, name='teacher_update'),
    path('<int:pk>/', views.teacher_detail, name='teacher_detail'),

    # 근무 및 급여 관리
    path('work/bulk/', views.teacher_bulk_work, name='teacher_bulk_work'),
    # 지급 처리
    path('payroll/process/', views.teacher_payroll_process, name='teacher_payroll_process'),
    path('payroll/bulk-process/', views.teacher_payroll_bulk_process, name='teacher_payroll_bulk_process'),
    path('payroll/delete-record/', views.teacher_payroll_delete_record, name='teacher_payroll_delete_record'),

    # 급여 계산 페이지
    path('payroll/', views.teacher_payroll, name='teacher_payroll'),
    path('payroll/pdf/', views.teacher_payroll_pdf, name='teacher_payroll_pdf'),

    # API 및 상세 PDF
    path('<int:pk>/history/pdf/', views.teacher_work_history_pdf, name='teacher_work_history_pdf'),
    path('api/check-availability/', views.check_availability_api, name='check_availability_api'),

    # 연도별 지급 내역
    path('payroll/annual/', views.teacher_payroll_year_list, name='teacher_payroll_year_list'),
]