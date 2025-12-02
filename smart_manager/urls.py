# smart_manager/urls.py

from django.contrib import admin
from django.urls import path, include

# static, settings import
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # 인증(로그인/로그아웃) URL - Django 내장 기능 활용
    path('accounts/', include('django.contrib.auth.urls')),
    # /students/ 로 시작하는 모든 URL은 students.urls로 연결
    path('students/', include('students.urls')),
    # /teachers/
    path('teachers/', include('teachers.urls')),
    # bookstore
    path('bookstore/', include('bookstore.urls')),
    # classes
    path('classes/', include('classes.urls')),
    # schedule
    path('schedule/', include('schedule.urls')),
    # 메인 대시보드 (가장 마지막에 두는 것이 좋습니다)
    path('', include('core.urls')),
]

# 개발 환경에서 미디어 파일 서빙을 위한 URL
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)