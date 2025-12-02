# classes/views.py

from django.shortcuts import render, redirect, get_object_or_404
from .models import ClassInfo, TuitionLog
from .forms import ClassForm, ClassDropForm
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from students.models import Student
import calendar


# ==========================================
# 수업(Class) 기본 CRUD
# ==========================================

def class_list(request):
    """수업 목록 조회"""
    classes = ClassInfo.objects.all().order_by('-is_active', 'name')
    return render(request, 'classes/class_list.html', {'classes': classes})


def class_create(request):
    """신규 수업 개설 (학년별 목록 + 기준일 일할 계산)"""
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    new_class = form.save()

                    # 폼에서 입력받은 날짜 사용 (없으면 오늘)
                    enroll_date = form.cleaned_data.get('enrollment_date') or timezone.localtime(timezone.now()).date()

                    students = form.cleaned_data['students']

                    count = 0
                    for student in students:
                        # --- 일할 계산 로직 (기준일: enroll_date) ---
                        if enroll_date.day == 1:
                            charge_amount = new_class.tuition_fee
                            memo_text = f"{enroll_date.month}월 수강신청 (개강)"
                        else:
                            _, last_day = calendar.monthrange(enroll_date.year, enroll_date.month)
                            remain_days = last_day - enroll_date.day + 1
                            charge_amount = int((new_class.tuition_fee * (remain_days / last_day)) // 1000) * 1000
                            memo_text = f"{enroll_date.month}월 수강신청 ({enroll_date.day}일~말일)"

                        TuitionLog.objects.create(
                            student=student,
                            class_info=new_class,
                            amount=charge_amount,
                            charge_date=enroll_date,
                            month=f"{enroll_date.month}월 수강료",
                            memo=memo_text
                        )
                        student.unpaid_amount += charge_amount
                        student.save()
                        count += 1

                    messages.success(request, f"수업 개설 완료! 학생 {count}명에게 {enroll_date} 기준 수강료가 청구되었습니다.")
                    return redirect('class_list')
            except Exception as e:
                messages.error(request, f"오류 발생: {e}")
    else:
        form = ClassForm()

    # [핵심] 학년별로 보여주기 위해 모든 학생 명단을 컨텍스트에 담아 보냄
    all_students = Student.objects.all().order_by('grade', 'name')

    return render(request, 'classes/class_form.html', {
        'form': form,
        'title': '👨‍🏫 신규 수업 개설',
        'all_students': all_students,  # 템플릿에서 regroup 사용 예정
        'selected_ids': []  # 신규니까 선택된 학생 없음
    })


def class_update(request, pk):
    """수업 정보 수정 (학년별 목록 + 수강생 변경 시 일할 계산)"""
    class_obj = get_object_or_404(ClassInfo, pk=pk)

    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            try:
                with transaction.atomic():
                    old_students = set(class_obj.students.all())
                    updated_class = form.save()
                    new_students = set(form.cleaned_data['students'])

                    # 폼에서 입력받은 날짜 사용
                    enroll_date = form.cleaned_data.get('enrollment_date') or timezone.localtime(timezone.now()).date()

                    to_add = new_students - old_students
                    to_remove = old_students - new_students

                    # [추가된 학생] -> enroll_date 기준으로 청구
                    for student in to_add:
                        if enroll_date.day == 1:
                            charge_amount = updated_class.tuition_fee
                            memo_text = f"{enroll_date.month}월 수강신청"
                        else:
                            _, last_day = calendar.monthrange(enroll_date.year, enroll_date.month)
                            remain_days = last_day - enroll_date.day + 1
                            charge_amount = int((updated_class.tuition_fee * (remain_days / last_day)) // 1000) * 1000
                            memo_text = f"{enroll_date.month}월 수강신청 ({enroll_date.day}일~말일)"

                        TuitionLog.objects.create(
                            student=student,
                            class_info=updated_class,
                            amount=charge_amount,
                            charge_date=enroll_date,
                            month=f"{enroll_date.month}월 수강료",
                            memo=memo_text
                        )
                        student.unpaid_amount += charge_amount
                        student.save()

                    # [삭제된 학생] -> 미납 내역 삭제 (기존 로직)
                    for student in to_remove:
                        unpaid_logs = TuitionLog.objects.filter(student=student, class_info=updated_class,
                                                                is_paid=False)
                        for log in unpaid_logs:
                            student.unpaid_amount -= log.amount
                            log.delete()
                        student.save()

                    msg = f"수업 정보 수정 완료. (추가 {len(to_add)}명, 삭제 {len(to_remove)}명)"
                    messages.success(request, msg)
                    return redirect('class_list')

            except Exception as e:
                messages.error(request, f"오류 발생: {e}")
    else:
        form = ClassForm(instance=class_obj)

    all_students = Student.objects.all().order_by('grade', 'name')
    # [핵심] 이미 수강 중인 학생들의 ID 리스트를 뽑아서 템플릿으로 보냄 (체크박스 미리 체크용)
    selected_ids = list(class_obj.students.values_list('id', flat=True))

    return render(request, 'classes/class_form.html', {
        'form': form,
        'title': f'수업 수정: {class_obj.name}',
        'all_students': all_students,
        'selected_ids': selected_ids
    })


def class_delete(request, pk):
    """수업 삭제"""
    class_obj = get_object_or_404(ClassInfo, pk=pk)
    if request.method == 'POST':
        class_obj.delete()
        return redirect('class_list')
    return redirect('class_list')


# ==========================================
# 학생 수강 및 청구 관리 (심플하고 강력한 버전으로 복구)
# ==========================================

def student_class_drop(request, student_pk, class_pk):
    """학생 수강 취소 및 미납 내역 자동 삭제"""
    student = get_object_or_404(Student, pk=student_pk)
    class_obj = get_object_or_404(ClassInfo, pk=class_pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. 수강 목록에서 제거
                student.enrolled_classes.remove(class_obj)

                # 2. 이 수업과 관련된 '미납(Unpaid)' 청구 내역을 모두 찾음
                unpaid_logs = TuitionLog.objects.filter(
                    student=student,
                    class_info=class_obj,
                    is_paid=False
                )

                # 3. 삭제할 금액 합계 계산
                refund_amount = sum(log.amount for log in unpaid_logs)

                # 4. 내역 삭제
                unpaid_logs.delete()

                # 5. 학생 장부(미납 총액)에서 차감
                if refund_amount > 0:
                    student.unpaid_amount -= refund_amount
                    student.save()
                    messages.warning(request, f"'{class_obj.name}' 수강 취소. 미납된 수강료 {refund_amount:,}원이 삭제되었습니다.")
                else:
                    messages.info(request, f"'{class_obj.name}' 수강이 취소되었습니다.")

        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    return redirect('student_detail', pk=student_pk)


def tuition_charge(request, student_pk, class_pk):
    """개별 수강료 청구"""
    student = get_object_or_404(Student, pk=student_pk)
    class_obj = get_object_or_404(ClassInfo, pk=class_pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. 수강료 기록 생성
                TuitionLog.objects.create(
                    student=student,
                    class_info=class_obj,
                    amount=class_obj.tuition_fee,
                    charge_date=timezone.localtime(timezone.now()).date(),
                    month=f"{timezone.localtime(timezone.now()).month}월 수강료"
                )
                # 2. 학생 미납금 증가
                student.unpaid_amount += class_obj.tuition_fee
                student.save()
                messages.success(request, f"'{class_obj.name}' 수강료가 청구되었습니다.")
        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    return redirect('student_detail', pk=student_pk)


def tuition_settle(request, log_pk):
    """수강료 납부 처리"""
    log = get_object_or_404(TuitionLog, pk=log_pk)

    if request.method == 'POST':
        payment_date = request.POST.get('payment_date')
        try:
            with transaction.atomic():
                log.is_paid = True
                log.payment_date = payment_date
                log.save()

                log.student.unpaid_amount -= log.amount
                log.student.save()

                messages.success(request, "수강료 납부 처리가 완료되었습니다.")
        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    return redirect('student_detail', pk=log.student.pk)


# [추가] 일괄 청구 뷰 (유지)
def monthly_batch_charge(request):
    if request.method == 'POST':
        today = timezone.localtime(timezone.now()).date()
        target_month = f"{today.month}월 수강료"
        count = 0
        try:
            with transaction.atomic():
                active_classes = ClassInfo.objects.filter(is_active=True)
                for class_obj in active_classes:
                    for student in class_obj.students.all():
                        if not TuitionLog.objects.filter(student=student, class_info=class_obj,
                                                         month=target_month).exists():
                            TuitionLog.objects.create(
                                student=student, class_info=class_obj, amount=class_obj.tuition_fee,
                                charge_date=today, month=target_month, memo="정기 일괄 청구"
                            )
                            student.unpaid_amount += class_obj.tuition_fee
                            student.save()
                            count += 1
            messages.success(request, f"총 {count}건의 수강료가 일괄 청구되었습니다.")
        except Exception as e:
            messages.error(request, f"오류: {e}")
    return redirect('dashboard')

