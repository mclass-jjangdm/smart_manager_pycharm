# teachers/views.py
import os
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from .models import Teacher, TeacherWorkRecord, TeacherUnavailable, TeacherPaymentRecord
from .forms import TeacherForm, WorkRecordForm, UnavailableForm
from django.contrib import messages # 알림 메시지
from django.utils import timezone
from collections import defaultdict # dictionary 편의 기능
from django.http import JsonResponse # JSON 응답용
# PDF 생성을 위한 필수 라이브러리 임포트
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse
import datetime
from django.urls import reverse
from django.db.models import Sum, Count


def teacher_list(request):
    """교사 목록 조회 (퇴사자 필터링 기능 추가)"""

    # 1. 체크박스 값 확인 ('on'이면 체크된 상태)
    show_retired = request.GET.get('show_retired') == 'on'

    # 2. 기본 쿼리셋 (모든 교사)
    teachers = Teacher.objects.all().order_by('-hire_date')

    # 3. 체크박스가 꺼져있으면(False), 퇴사일이 없는(현직) 교사만 필터링
    if not show_retired:
        teachers = teachers.filter(resign_date__isnull=True)

    context = {
        'teachers': teachers,
        'show_retired': show_retired,  # 템플릿에서 체크박스 상태 유지를 위해 전달
    }
    return render(request, 'teachers/teacher_list.html', context)


def teacher_create(request):
    """교사 등록"""
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('teacher_list')
    else:
        form = TeacherForm()

    context = {'form': form, 'title': '👨‍🏫 신규 교사 등록'}
    return render(request, 'teachers/teacher_form.html', context)


def teacher_update(request, pk):
    """교사 정보 수정"""
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            return redirect('teacher_list')
    else:
        form = TeacherForm(instance=teacher)

    context = {'form': form, 'title': f'👨‍🏫 교사 정보 수정: {teacher.name}'}
    return render(request, 'teachers/teacher_form.html', context)


def teacher_detail(request, pk):
    """교사 상세 및 근무 관리 뷰"""
    teacher = get_object_or_404(Teacher, pk=pk)

    # 1. POST 요청 처리 (폼 제출)
    if request.method == 'POST':
        # action 이라는 hidden input 값으로 어떤 폼인지 구분합니다.
        action = request.POST.get('action')

        if action == 'work_record':
            form = WorkRecordForm(request.POST)
            if form.is_valid():
                record = form.save(commit=False)
                record.teacher = teacher  # 현재 교사 연결
                record.save()
                return redirect('teacher_detail', pk=pk)

        elif action == 'unavailable':
            form = UnavailableForm(request.POST)
            if form.is_valid():
                unavailable = form.save(commit=False)
                unavailable.teacher = teacher
                unavailable.save()
                return redirect('teacher_detail', pk=pk)

        elif action == 'delete_work':
            # 근무 기록 삭제
            record_id = request.POST.get('record_id')
            record = get_object_or_404(TeacherWorkRecord, pk=record_id)
            record.delete()
            return redirect('teacher_detail', pk=pk)

        # [추가] 근무 불가 일정 삭제 로직
        elif action == 'delete_unavailable':
            unavailable_id = request.POST.get('unavailable_id')
            unavailable_obj = get_object_or_404(TeacherUnavailable, pk=unavailable_id)
            unavailable_obj.delete()
            return redirect('teacher_detail', pk=pk)

    # 2. GET 요청 처리 (페이지 조회)
    # 빈 폼 생성
    work_form = WorkRecordForm(initial={
        'date' : timezone.now().date(),
        'start_time': '18:00',  # 기본값 18:00
        'end_time': '20:00'  # 기본값 20:00
    })
    unavailable_form = UnavailableForm()

    # 목록 조회
    work_records = teacher.work_records.all().order_by('-date')
    unavailable_dates = teacher.unavailable_dates.all().order_by('-date')

    # 월별 근무 시간 합계 계산 로직
    monthly_summary = defaultdict(float)  # 기본값이 0.0인 딕셔너리
    for record in work_records:
        # '2025-11' 형태의 키 생성
        month_key = record.date.strftime('%Y-%m')
        # 모델의 get_work_hours() 메서드 결과 더하기
        monthly_summary[month_key] += record.get_work_hours()

    # 템플릿에서 보기 좋게 정렬 (최신 월 순서)
    sorted_summary = dict(sorted(monthly_summary.items(), reverse=True))

    context = {
        'teacher': teacher,
        'work_form': work_form,
        'unavailable_form': unavailable_form,
        'work_records': work_records,
        'unavailable_dates': unavailable_dates,
        'monthly_summary': sorted_summary,  # 템플릿으로 전달
    }
    return render(request, 'teachers/teacher_detail.html', context)


def teacher_bulk_work(request):
    """교사 근무 기록 일괄 입력 뷰 (퇴사자 제외)"""

    # resign_date가 NULL인 (퇴사일이 없는 = 현직인) 교사만 가져옵니다.
    teachers = Teacher.objects.filter(resign_date__isnull=True).order_by('name')

    if request.method == 'POST':
        # 1. 공통 데이터 받기 (날짜, 비고)
        date = request.POST.get('date')
        memo = request.POST.get('memo')

        # 2. 체크박스로 선택된 교사 ID 리스트 받기
        selected_ids = request.POST.getlist('teacher_ids')

        if not selected_ids:
            messages.error(request, "선택된 교사가 없습니다.")
            return redirect('teacher_bulk_work')

        count = 0
        for t_id in selected_ids:
            # 3. 각 교사별로 입력된 시작/종료 시간 가져오기
            start = request.POST.get(f'start_time_{t_id}')
            end = request.POST.get(f'end_time_{t_id}')

            if start and end:  # 시간이 입력된 경우에만 저장
                teacher = Teacher.objects.get(pk=t_id)
                TeacherWorkRecord.objects.create(
                    teacher=teacher,
                    date=date,
                    start_time=start,
                    end_time=end,
                    memo=memo
                )
                count += 1

        messages.success(request, f'{count}명의 근무 기록이 저장되었습니다.')
        return redirect('teacher_list')

    # GET 요청 시: 오늘 날짜를 기본값으로 전달
    context = {
        'teachers': teachers,
        'today': timezone.now().strftime('%Y-%m-%d')
    }
    return render(request, 'teachers/teacher_bulk_work.html', context)


def check_availability_api(request):
    """특정 날짜의 근무 불가 교사 ID 목록을 반환하는 API"""
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'unavailable_ids': []})

    # 해당 날짜에 등록된 '근무 불가' 기록 조회
    unavailable_records = TeacherUnavailable.objects.filter(date=date_str)

    # 교사 ID 리스트 추출
    unavailable_ids = list(unavailable_records.values_list('teacher_id', flat=True))

    return JsonResponse({'unavailable_ids': unavailable_ids})


def calculate_payroll_data(year, month):
    """급여 계산 공통 함수"""
    teachers = Teacher.objects.all().order_by('name')
    payroll_data = []

    for teacher in teachers:
        hire_date = teacher.hire_date
        # 1. 입사 연도 체크: 계산 연도가 입사 연도보다 이전이면 건너뛰기
        if year < hire_date.year:
            continue
        # 2. 입사 월 체크: 연도가 같고, 계산 월이 입사 월보다 이전이면 건너뛰기
        if year == hire_date.year and month < hire_date.month:
            continue
        records = teacher.work_records.filter(date__year=year, date__month=month)
        work_days = records.count()
        total_hours = sum(r.get_work_hours() for r in records)
        base_salary = total_hours * teacher.base_pay
        total_salary = base_salary + teacher.extra_pay

        # 해당 월의 지급 기록이 있는지 확인
        payment_record = TeacherPaymentRecord.objects.filter(
            teacher=teacher, year=year, month=month
        ).first()

        is_paid = payment_record.is_paid if payment_record else False
        payment_date = payment_record.payment_date if payment_record else None

        if work_days > 0 or teacher.extra_pay > 0:
            payroll_data.append({
                'teacher': teacher,
                'bank_name': teacher.bank_name,
                'account_number': teacher.account_number,
                'work_days': work_days,
                'work_hours': total_hours,
                'base_pay_rate': teacher.base_pay,
                'base_salary': int(base_salary),
                'extra_pay': teacher.extra_pay,
                'total_salary': int(total_salary),
                # 지급 상태 정보
                'is_paid': is_paid,
                'payment_date': payment_date,
            })
    return payroll_data


def teacher_payroll(request):
    """급여 조회 페이지"""
    now = datetime.datetime.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))

    payroll_data = calculate_payroll_data(year, month)

    # 이번 달 지급 대상 총액 계산
    grand_total = sum(item['total_salary'] for item in payroll_data)

    context = {
        'payroll_data': payroll_data,
        'year': year,
        'month': month,
        'year_range': range(now.year - 2, now.year + 2),
        'month_range': range(1, 13),
        'grand_total': grand_total,  # 템플릿으로 전달
    }
    return render(request, 'teachers/teacher_payroll.html', context)


def teacher_payroll_pdf(request):
    """급여 내역 전체 PDF"""
    now = datetime.datetime.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))

    payroll_data = calculate_payroll_data(year, month)

    response = HttpResponse(content_type='application/pdf')
    filename = f"급여내역_{year}_{month}월.pdf"
    # 한글 파일명 깨짐 방지를 위해 ASCII 처리
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # 사용자께서 설정하신 폰트 이름 사용
    font_name = 'MaruBuri-Regular'

    # 폰트 등록 (teacher_work_history_pdf 함수와 동일한 로직 사용)
    try:
        # settings.BASE_DIR는 views.py 상단에 import 되어 있어야 함
        pdfmetrics.registerFont(TTFont(font_name, os.path.join(settings.BASE_DIR, 'static', 'fonts', f'{font_name}.ttf')))
    except:
        font_name = 'Helvetica'

    # 문서 제목
    c.setFont(font_name, 16)
    c.drawString(200, height - 50, f"{year}년 {month}월 월간 급여 보고서")

    y = height - 80
    c.setFont(font_name, 10)

    c.line(30, y + 10, 560, y + 10)

    # 테이블 헤더
    c.drawString(30, y, "이름")

    c.line(30, y + 10, 560, y + 10)

    # c.drawString(120, y, "은행 / 계좌")
    c.drawString(280, y, "근무일")
    c.drawString(320, y, "시간")
    c.drawString(380, y, "지급액")

    y -= 20
    c.setFont(font_name, 10)

    total_payout = 0
    for data in payroll_data:
        if y < 50: # 페이지 분할
            c.showPage()
            y = height - 50

        c.drawString(30, y, str(data['teacher'].name))
        # c.drawString(120, y, f"{data['bank_name']} {data['account_number']}")
        c.drawString(280, y, str(data['work_days']))
        c.drawString(320, y, f"{data['work_hours']}h")
        # 천 단위 콤마 처리는 PDF에서 직접 하기 어려우므로 intcomma 대신 f-string 포맷 사용
        c.drawString(380, y, f"{data['total_salary']:,}원")

        total_payout += data['total_salary']
        y -= 20

    c.line(30, y + 10, 560, y + 10)
    c.setFont(font_name, 12)
    c.drawString(30, y - 10, "총 지급액:")
    c.drawString(380, y - 10, f"{total_payout:,}원")

    c.showPage()
    c.save()
    return response


def teacher_work_history_pdf(request, pk):
    """교사 개인별 월간 근무 기록 PDF 내보내기"""
    teacher = get_object_or_404(Teacher, pk=pk)

    # URL 파라미터로 'date' (예: "2025-11")를 받음
    date_str = request.GET.get('date')
    if not date_str:
        return HttpResponse("Invalid Date", status=400)

    year, month = map(int, date_str.split('-'))

    # 해당 월의 근무 기록 조회
    records = teacher.work_records.filter(date__year=year, date__month=month).order_by('-date')

    # PDF 생성 시작
    response = HttpResponse(content_type='application/pdf')
    filename = f"WorkHistory_{teacher.name}_{date_str}.pdf"
    # 한글 파일명 깨짐 방지를 위해 ASCII 처리 (선택사항)
    response['Content-Disposition'] = f'attachment; filename="WorkHistory_{year}_{month}.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # 한글 폰트 등록 (static/fonts/MaruBuri-Regular.ttf)
    font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'MaruBuri-Regular.ttf')
    try:
        pdfmetrics.registerFont(TTFont('MaruBuri-Regular', font_path))
        font_name = 'MaruBuri-Regular'
    except:
        # 폰트 파일이 없을 경우 기본 영문 폰트로 폴백 (에러 방지)
        font_name = 'Helvetica'
        print("Warning: MaruBuri-Regular font not found.")

    # 제목
    c.setFont(font_name, 16)  # 등록한 한글 폰트 사용
    c.drawString(250, height - 50, f"근무 기록")

    c.setFont(font_name, 12)
    c.drawString(30, height - 80, f"이름: {teacher.name}")
    c.drawString(30, height - 100, f"기간: {date_str}")

    # 테이블 헤더
    y = height - 140
    c.setFont(font_name, 10)
    c.drawString(30, y, "날짜")
    c.drawString(120, y, "시작")
    c.drawString(200, y, "종료")
    c.drawString(280, y, "시간")
    c.drawString(350, y, "비고")
    c.line(30, y - 5, 550, y - 5)

    # 데이터 출력
    y -= 25
    c.setFont(font_name, 10)

    total_hours = 0.0

    for record in records:
        if y < 50:  # 페이지 넘김
            c.showPage()
            c.setFont(font_name, 10)  # 새 페이지에서도 폰트 재설정
            y = height - 50

        hours = record.get_work_hours()
        total_hours += hours

        # 날짜 형식 (YYYY-MM-DD)
        c.drawString(30, y, record.date.strftime('%Y-%m-%d'))
        c.drawString(120, y, record.start_time.strftime('%H:%M'))
        c.drawString(200, y, record.end_time.strftime('%H:%M'))
        c.drawString(280, y, f"{hours} 시간")

        # 비고 (None이면 빈 문자열)
        memo = record.memo if record.memo else ""
        c.drawString(350, y, str(memo))

        y -= 20

    # 총계
    c.line(30, y + 10, 550, y + 10)
    c.setFont(font_name, 12)  # 강조를 위해 폰트 크기 키움
    c.drawString(30, y - 10, "총 근무 시간:")
    c.drawString(280, y - 10, f"{total_hours} 시간")

    # 서명란
    # c.drawString(30, y - 50, "서명: __________________________")

    c.showPage()
    c.save()

    return response


def teacher_payroll_process(request):
    """지급 처리 및 지급 기록 수정 로직 통합"""
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))
        amount = int(request.POST.get('amount'))  # total_salary
        payment_date_str = request.POST.get('payment_date')

        # 지급일 유효성 검사 및 변환
        try:
            payment_date = datetime.datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "지급일 형식 오류. YYYY-MM-DD 형식으로 입력해주세요.")
            return redirect(f"{reverse('teacher_payroll')}?year={year}&month={month}")

        teacher = get_object_or_404(Teacher, pk=teacher_id)

        # [핵심 수정] get_or_create를 사용하여 기록을 찾거나 생성합니다.
        record, created = TeacherPaymentRecord.objects.get_or_create(
            teacher=teacher,
            year=year,
            month=month,
            # 새로 생성될 경우의 기본값
            defaults={
                'amount_paid': amount,
                'payment_date': payment_date,
                'is_paid': True
            }
        )

        if created:
            messages.success(request,
                             f"{teacher.name} 선생님의 {year}년 {month}월 급여 지급이 {payment_date.strftime('%Y-%m-%d')} 날짜로 기록되었습니다.")
        else:
            # [수정 로직] 이미 기록이 있다면, 지급액과 지급일을 업데이트합니다.
            record.amount_paid = amount
            record.payment_date = payment_date
            record.is_paid = True  # 수정 시에도 지급 완료 상태 유지
            record.save()
            messages.success(request,
                             f"{teacher.name} 선생님의 {year}년 {month}월 급여 기록이 {payment_date.strftime('%Y-%m-%d')} 날짜로 수정되었습니다.")

    return redirect(f"{reverse('teacher_payroll')}?year={year}&month={month}")


def teacher_payroll_bulk_process(request):
    """미지급된 모든 급여 일괄 지급 처리"""
    if request.method == 'POST':
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))
        payment_date_str = request.POST.get('payment_date')

        # 지급일 유효성 검사 및 변환
        try:
            payment_date = datetime.datetime.strptime(payment_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "일괄 지급 처리 오류: 지급일 형식 오류.")
            return redirect(f"{reverse('teacher_payroll')}?year={year}&month={month}")

        # 급여 계산 데이터를 가져옵니다. (입사일 필터링 로직 포함)
        payroll_data = calculate_payroll_data(year, month)

        processed_count = 0

        for data in payroll_data:
            # 미지급 상태이고, 근무 기록 또는 추가 급여가 있는 경우에만 처리
            if not data['is_paid'] and (data['work_hours'] > 0 or data['extra_pay'] > 0):
                teacher = data['teacher']
                amount = data['total_salary']

                # get_or_create로 처리 (중복 방지 및 생성)
                record, created = TeacherPaymentRecord.objects.get_or_create(
                    teacher=teacher,
                    year=year,
                    month=month,
                    defaults={
                        'amount_paid': amount,
                        'payment_date': payment_date,
                        'is_paid': True
                    }
                )

                # 이미 존재하지만 is_paid=False로 되어있던 기록이 있다면 업데이트
                if not created:
                    record.amount_paid = amount
                    record.payment_date = payment_date
                    record.is_paid = True
                    record.save()

                processed_count += 1

        if processed_count > 0:
            messages.success(request,
                             f"{year}년 {month}월 미지급 급여 {processed_count}건이 {payment_date_str} 날짜로 일괄 지급 처리되었습니다.")
        else:
            messages.info(request, f"{year}년 {month}월에는 미지급된 급여가 없습니다.")

    return redirect(f"{reverse('teacher_payroll')}?year={year}&month={month}")


def teacher_payroll_delete_record(request):
    """지급 기록을 삭제하고 미지급 상태로 되돌림"""
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))

        # 특정 교사의 해당 월 지급 기록을 찾습니다.
        record = TeacherPaymentRecord.objects.filter(
            teacher_id=teacher_id, year=year, month=month
        ).first()

        if record:
            record.delete()
            messages.success(request, f"{record.teacher.name} 선생님의 {year}년 {month}월 지급 기록이 삭제되고 '미지급' 상태로 복구되었습니다.")
        else:
            messages.info(request, "삭제할 지급 기록을 찾을 수 없습니다. (이미 미지급 상태일 수 있습니다.)")

        # 기존 조회 페이지로 돌아가되, 필터링 조건 유지
        return redirect(f"{reverse('teacher_payroll')}?year={year}&month={month}")

    return redirect('teacher_payroll')


def teacher_payroll_year_list(request):
    """연간 급여 대장 (교사별/월별 매트릭스)"""
    now = datetime.datetime.now()
    selected_year = int(request.GET.get('year', now.year))

    # 1. 모든 교사 가져오기
    teachers = Teacher.objects.all().order_by('name')

    report_data = []
    # 월별 총합을 저장할 리스트 (0~11 인덱스 사용)
    monthly_totals = [0] * 12
    grand_total = 0

    for teacher in teachers:
        # 해당 연도의 지급 기록 가져오기 (지급 완료된 것만)
        payments = TeacherPaymentRecord.objects.filter(
            teacher=teacher,
            year=selected_year,
            is_paid=True
        )

        # 12개월치 0으로 초기화
        monthly_amounts = [0] * 12
        teacher_total = 0
        has_payment = False

        for p in payments:
            # month는 1~12이므로 인덱스는 month-1
            idx = p.month - 1
            if 0 <= idx < 12:
                monthly_amounts[idx] = p.amount_paid
                teacher_total += p.amount_paid

                # 세로 합계(월별 총합) 누적
                monthly_totals[idx] += p.amount_paid
                has_payment = True

        # 1년 동안 한 번이라도 지급 내역이 있는 교사만 리포트에 포함
        if has_payment:
            report_data.append({
                'teacher': teacher,
                'monthly_amounts': monthly_amounts,  # [1월액, 2월액, ... 12월액]
                'row_total': teacher_total
            })
            grand_total += teacher_total

    context = {
        'report_data': report_data,
        'monthly_totals': monthly_totals,
        'grand_total': grand_total,
        'selected_year': selected_year,
        'year_range': range(now.year - 2, now.year + 2),
    }
    return render(request, 'teachers/teacher_payroll_year.html', context)

