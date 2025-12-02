# students/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # 학생 목록 페이지 ( /students/ )
    path('', views.student_list, name='student_list'),

    # 학생 등록 페이지 ( /students/new/ )
    path('new/', views.student_create, name='student_create'),

    # 학생 상세 페이지 ( /students/1/, /students/2/ ... )
    path('<int:pk>/', views.student_detail, name='student_detail'),

    # 학생 수정 URL (예: /students/1/edit/)
    path('<int:pk>/edit/', views.student_update, name='student_update'),

    # 파일 삭제 URL (예: /students/file/5/delete/ )
    path('file/<int:file_pk>/delete/', views.delete_student_file, name='delete_student_file'),

    # 일괄 등록 페이지
    path('upload/', views.student_bulk_upload, name='student_bulk_upload'),

    # 데이터 내보내기 URL
    path('export/', views.student_export, name='student_export'),

    # 문자
    path('<int:pk>/sms/', views.student_sms_send, name='student_sms_send'),

    # 수업
    path('<int:pk>/classes/', views.student_class_edit, name='student_class_edit'),

    path('<int:pk>/delete/', views.student_delete, name='student_delete'),

]