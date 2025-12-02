# students/views.py

from django.shortcuts import render, redirect, get_object_or_404
from .models import Student, StudentFile
from .forms import StudentForm, StudentFileForm, SMSForm, StudentClassForm
import pandas as pd
from django.http import HttpResponse
from datetime import datetime
from django.contrib import messages
from core.utils import send_sms # 문자 발송 함수
from django.db import transaction
from django.utils import timezone
from classes.models import TuitionLog
from classes.models import ClassInfo
import calendar # 이번 달이 며칠까지 있는지 알기 위해 필요


def student_list(request):
    """학생 목록 조회 뷰 (R)"""
    # 모든 학생 객체를 'created_at'(등록일)의 역순으로 가져옵니다.
    students = Student.objects.all().order_by('-created_at')

    # 'student_list.html' 템플릿에 학생 목록을 담아 전달합니다.
    context = {
        'students': students,
    }
    return render(request, 'students/student_list.html', context)


def student_create(request):
    """학생 등록 뷰 (C)"""
    if request.method == 'POST':
        # 사용자가 폼을 채우고 '저장' 버튼을 눌렀을 때 (POST 방식)
        form = StudentForm(request.POST)
        if form.is_valid():
            # 폼 데이터가 유효하면
            form.save()  # 데이터베이스에 저장
            return redirect('student_list')  # 학생 목록 페이지로 이동
    else:
        # 사용자가 '학생 등록' 페이지에 처음 접속했을 때 (GET 방식)
        form = StudentForm()  # 빈 폼을 생성

    # 'student_form.html' 템플릿에 폼을 담아 전달합니다.
    context = {
        'form': form,
    }
    return render(request, 'students/student_form.html', context)


def student_update(request, pk):
    """학생 정보 수정 뷰 (U)"""
    # pk로 수정할 학생 객체를 가져옵니다.
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        # [핵심] instance=student를 넣어주면, 기존 정보를 덮어쓰는 수정 모드가 됩니다.
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            # 수정 후에는 해당 학생의 상세 페이지로 이동
            return redirect('student_detail', pk=student.pk)
    else:
        # GET 요청 시 기존 정보가 채워진 폼을 보여줍니다.
        form = StudentForm(instance=student)

    context = {
        'form': form,
        'student': student, # 템플릿에서 '수정'인지 '등록'인지 구분하기 위해 전달
    }
    # 기존 student_form.html을 재사용합니다.
    return render(request, 'students/student_form.html', context)


def student_detail(request, pk):
    """학생 상세 정보 및 파일/교재/수강료 관리"""
    student = get_object_or_404(Student, pk=pk)

    # [수정] 파일 업로드 처리 로직 (다중 파일 지원)
    if request.method == 'POST' and request.FILES:
        # 폼 데이터 가져오기 (설명은 공통으로 적용됨)
        description = request.POST.get('description', '')

        # 'file' 필드로 들어온 모든 파일 가져오기
        files = request.FILES.getlist('file')

        if files:
            for f in files:
                # 각각의 파일에 대해 모델 생성
                StudentFile.objects.create(
                    student=student,
                    file=f,
                    description=description
                )
            messages.success(request, f"{len(files)}개의 파일이 업로드되었습니다.")
            return redirect('student_detail', pk=pk)

    # GET 요청이거나 파일 업로드가 아닐 때 기본 폼 로드
    file_form = StudentFileForm()

    # 1. 파일 목록
    files = student.files.all().order_by('-uploaded_at')

    # 2. 미납금 상세 내역 계산
    unpaid_book_sales = student.book_sales.filter(is_paid=False)
    unpaid_book_total = sum(sale.get_total_price() for sale in unpaid_book_sales)
    unpaid_tuition_total = max(0, student.unpaid_amount - unpaid_book_total)

    return render(request, 'students/student_detail.html', {
        'student': student,
        'files': files,
        'file_form': file_form,
        'unpaid_book_total': unpaid_book_total,
        'unpaid_tuition_total': unpaid_tuition_total,
    })


def student_delete(request, pk):
    """학생 기록 완전 삭제"""
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        name = student.name
        student.delete()
        messages.warning(request, f"학생 '{name}'의 모든 기록이 삭제되었습니다.")
        return redirect('student_list')

    return redirect('student_detail', pk=pk)


# 파일 삭제 뷰
def delete_student_file(request, file_pk):
    """학생 파일 삭제 뷰"""
    # file_pk로 삭제할 파일 객체를 찾습니다.
    file_to_delete = get_object_or_404(StudentFile, pk=file_pk)
    student_pk = file_to_delete.student.pk  # 삭제 후 돌아갈 학생의 pk 저장

    if request.method == 'POST':
        # 실제 파일 시스템에서 파일을 삭제합니다. (중요)
        file_to_delete.file.delete()
        # 데이터베이스에서 파일 기록을 삭제합니다.
        file_to_delete.delete()
        # 상세 페이지로 리다이렉트
        return redirect('student_detail', pk=student_pk)

    # GET 요청 시 (보통 삭제 확인 페이지)
    # 여기서는 간단히 구현하기 위해 POST만 처리하고,
    # 템플릿에서는 JS confirm()으로 대체합니다.
    return redirect('student_detail', pk=student_pk)


def student_bulk_upload(request):
    """엑셀/CSV 파일을 통한 학생 일괄 등록 뷰"""
    if request.method == 'POST' and request.FILES.get('upload_file'):
        upload_file = request.FILES['upload_file']

        try:
            # 파일 확장자에 따라 읽기 방식 분기
            if upload_file.name.endswith('.csv'):
                df = pd.read_csv(upload_file)
            else:
                df = pd.read_excel(upload_file)

            # 데이터프레임의 각 행(row)을 반복하며 학생 생성
            # [주의] 엑셀 파일의 컬럼명(헤더)이 아래와 같아야 합니다.
            success_count = 0
            for index, row in df.iterrows():
                # 필수 값(이름, 학년, 성별)이 없으면 건너뜀 (에러 방지)
                if pd.isna(row.get('이름')) or pd.isna(row.get('학년')):
                    continue

                # 성별 변환 (예: '남' -> 'M', '여' -> 'F')
                gender_input = str(row.get('성별', '')).strip()
                gender = 'M' if gender_input in ['남', 'M', 'Male'] else 'F'

                Student.objects.create(
                    name=row.get('이름'),
                    school=row.get('학교', ''),
                    grade=row.get('학년'),  # K5 ~ K12
                    gender=gender,
                    student_phone=row.get('학생 전화번호', ''),
                    parent_phone=row.get('부모님 전화번호', ''),
                    email=row.get('이메일', ''),
                    # 필요한 필드 추가 매핑 가능
                )
                success_count += 1

            messages.success(request, f'{success_count}명의 학생이 성공적으로 등록되었습니다.')
            return redirect('student_list')

        except Exception as e:
            # 에러 발생 시 메시지 표시
            messages.error(request, f'파일 업로드 중 오류가 발생했습니다: {e}')
            return redirect('student_bulk_upload')

    return render(request, 'students/student_upload.html')


def student_export(request):
    """학생 데이터를 엑셀 파일로 내보내는 뷰"""
    # 1. 모든 학생 데이터 조회
    students = Student.objects.all().order_by('-created_at')

    # 2. 데이터프레임 생성을 위한 리스트 만들기
    data = []
    for s in students:
        data.append({
            '고유번호': s.student_number,
            '이름': s.name,
            '학교': s.school,
            '학년': s.grade,
            '성별': s.get_gender_display(),
            '학생 전화번호': s.student_phone,
            '부모님 전화번호': s.parent_phone,
            '이메일': s.email,
            '현금영수증 번호': s.receipt_phone,
            '인터뷰 날짜': s.interview_date,
            '인터뷰 성적': s.interview_score,
            '인터뷰 정보': s.interview_info,
            '첫 수업 날짜': s.first_class_date,
            '그만 둔 날짜': s.last_class_date,
            '기타': s.misc,
            '등록일': s.created_at.strftime('%Y-%m-%d'),
        })

    # 3. Pandas DataFrame 생성
    df = pd.DataFrame(data)

    # 4. 응답(Response) 객체 생성 (엑셀 파일 형식)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # 5. 파일 이름 생성 (현재 날짜와 시간 이용)
    # 예: Student_DB_20251119_143000.xlsx
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'Student_DB_{current_time}.xlsx'

    # 6. 헤더 설정 (다운로드 창 띄우기)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # 7. 데이터프레임을 엑셀로 변환하여 응답에 쓰기
    df.to_excel(response, index=False)

    return response


def student_sms_send(request, pk):
    """학생/학부모에게 문자 발송"""
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        form = SMSForm(request.POST)
        if form.is_valid():
            target = form.cleaned_data['target']
            message = form.cleaned_data['message']

            success_count = 0
            fail_messages = []

            # 1. 학생에게 발송
            if target in ['student', 'both'] and student.student_phone:
                # 하이픈 제거
                phone = student.student_phone.replace('-', '').strip()
                is_success, msg = send_sms(phone, message)
                if is_success:
                    success_count += 1
                else:
                    fail_messages.append(f"학생: {msg}")

            # 2. 학부모에게 발송
            if target in ['parent', 'both'] and student.parent_phone:
                phone = student.parent_phone.replace('-', '').strip()
                is_success, msg = send_sms(phone, message)
                if is_success:
                    success_count += 1
                else:
                    fail_messages.append(f"부모님: {msg}")

            # 결과 메시지 처리
            if success_count > 0:
                messages.success(request, f"{success_count}건의 문자를 발송했습니다.")

            if fail_messages:
                for f_msg in fail_messages:
                    messages.error(request, f_msg)

            return redirect('student_detail', pk=student.pk)
    else:
        # 기본 폼
        form = SMSForm(initial={'target': 'student'})

    return render(request, 'students/student_sms_form.html', {
        'form': form,
        'student': student
    })


def student_class_edit(request, pk):
    """학생 수강 신청 관리 (선택한 날짜 기준 일할 계산 적용)"""
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        form = StudentClassForm(request.POST)
        if form.is_valid():
            new_classes = set(form.cleaned_data['classes'])
            current_classes = set(student.enrolled_classes.all())

            # [중요] 사용자가 폼에서 선택한 '수강 시작일' 가져오기
            start_date = form.cleaned_data['start_date']

            to_add = new_classes - current_classes
            to_remove = current_classes - new_classes

            # 선택한 날짜가 속한 달의 마지막 날짜 계산 (예: 11월 -> 30일)
            _, last_day_of_month = calendar.monthrange(start_date.year, start_date.month)

            try:
                with transaction.atomic():
                    # [로직 1] 추가된 수업: 'start_date' 기준으로 일할 계산
                    for class_obj in to_add:
                        # 1일이면 전액, 아니면 일할 계산
                        if start_date.day == 1:
                            charge_amount = class_obj.tuition_fee
                            memo_text = f"{start_date.month}월 수강신청"
                        else:
                            # 공식: 수강료 * (남은일수 / 총일수)
                            remaining_days = last_day_of_month - start_date.day + 1
                            calculated = class_obj.tuition_fee * (remaining_days / last_day_of_month)

                            # [요청사항] 1000원 단위 절사 (내림)
                            # 예: 85,333원 -> 85,000원
                            charge_amount = int(calculated // 1000) * 1000

                            memo_text = f"{start_date.month}월 수강신청 ({start_date.day}일~말일 일할계산)"

                        TuitionLog.objects.create(
                            student=student,
                            class_info=class_obj,
                            amount=charge_amount,
                            # [중요] 오늘 날짜가 아니라 '선택한 날짜'로 기록
                            charge_date=start_date,
                            month=f"{start_date.month}월 수강료",
                            memo=memo_text
                        )
                        student.unpaid_amount += charge_amount

                    # [로직 2] 취소된 수업: 미납 상태인 청구서 삭제 (기존 동일)
                    for class_obj in to_remove:
                        unpaid_logs = TuitionLog.objects.filter(
                            student=student,
                            class_info=class_obj,
                            is_paid=False
                        )
                        for log in unpaid_logs:
                            student.unpaid_amount -= log.amount
                            log.delete()

                    student.save()
                    student.enrolled_classes.set(new_classes)

                    messages.success(request, f"수강 내역이 변경되었습니다. (기준일: {start_date})")

            except Exception as e:
                messages.error(request, f"처리 중 오류 발생: {e}")

            return redirect('student_detail', pk=pk)
    else:
        form = StudentClassForm(initial={
            'classes': student.enrolled_classes.all(),
            'start_date': timezone.localtime(timezone.now()).date()
        })

    return render(request, 'students/student_class_form.html', {
        'form': form,
        'student': student
    })


def student_class_drop(request, student_pk, class_pk):
    """학생 수강 취소 및 미납 내역 자동 삭제"""
    student = get_object_or_404(Student, pk=student_pk)
    class_obj = get_object_or_404(ClassInfo, pk=class_pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. 수강 목록에서 제거
                student.enrolled_classes.remove(class_obj)

                # 2. 미납된 청구 내역이 있다면 찾아서 삭제 및 금액 차감
                unpaid_logs = TuitionLog.objects.filter(
                    student=student,
                    class_info=class_obj,
                    is_paid=False
                )

                refund_amount = 0
                for log in unpaid_logs:
                    refund_amount += log.amount
                    log.delete()

                if refund_amount > 0:
                    student.unpaid_amount -= refund_amount
                    student.save()
                    messages.warning(request, f"'{class_obj.name}' 수강 취소 및 미납액({refund_amount}원)이 차감되었습니다.")
                else:
                    messages.info(request, f"'{class_obj.name}' 수강이 취소되었습니다.")

        except Exception as e:
            messages.error(request, f"오류 발생: {e}")

    return redirect('student_detail', pk=student_pk)


