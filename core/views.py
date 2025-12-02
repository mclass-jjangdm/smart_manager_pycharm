# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone

# 각 앱의 모델들을 가져옵니다
from students.models import Student
from teachers.models import Teacher
from bookstore.models import Book, BookStockLog


@login_required  # 로그인한 사람만 접속 가능!
def dashboard(request):
    """메인 대시보드: 학원 현황 요약"""

    # 1. 학생 통계
    total_students = Student.objects.count()
    total_unpaid = Student.objects.aggregate(Sum('unpaid_amount'))['unpaid_amount__sum'] or 0

    # 2. 교사 통계
    total_teachers = Teacher.objects.count()

    # 3. 서점 통계
    # 재고가 5권 이하인 책 목록 (재고 부족 알림용)
    low_stock_books = Book.objects.filter(stock__lte=5, stock__gt=0).order_by('stock')
    # 품절된 책
    out_of_stock_books = Book.objects.filter(stock=0).count()

    # 4. 최근 입고/반품 활동 (최근 5건)
    recent_logs = BookStockLog.objects.all().order_by('-created_at')[:5]

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_unpaid': total_unpaid,
        'low_stock_books': low_stock_books,
        'out_of_stock_count': out_of_stock_books,
        'recent_logs': recent_logs,
    }

    return render(request, 'core/dashboard.html', context)