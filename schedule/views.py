# schedule/views.py

from django.shortcuts import render
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import calendar
import datetime
import json

from teachers.models import Teacher, TeacherUnavailable  # [추가] 휴무 모델 임포트
from students.models import Student
from .models import DailySchedule, DailyLog


def monthly_schedule(request):
    """월간 스케줄 조회 (휴무 모델 연동)"""
    today = timezone.localtime(timezone.now()).date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    _, last_day = calendar.monthrange(year, month)
    dates = [datetime.date(year, month, day) for day in range(1, last_day + 1)]

    teachers = Teacher.objects.filter(status='ACTIVE').order_by('name')
    all_students = Student.objects.filter(status='ATTENDING').order_by('name')

    # 1. 스케줄 데이터 로드
    schedules = DailySchedule.objects.filter(date__year=year, date__month=month).prefetch_related('assigned_students')
    schedule_map = {(s.date, s.teacher_id): s for s in schedules}

    # 2. 로그 데이터 로드
    logs = DailyLog.objects.filter(date__year=year, date__month=month).prefetch_related('absent_students',
                                                                                        'late_students',
                                                                                        'exception_students')
    log_map = {l.date: l for l in logs}

    # 3. [핵심] 휴무 데이터 로드 (TeacherUnavailable)
    unavailables = TeacherUnavailable.objects.filter(date__year=year, date__month=month)
    # (날짜, 교사ID)를 키로 하는 집합(Set) 생성 -> 빠른 조회용
    unavailable_set = {(u.date, u.teacher_id) for u in unavailables}

    schedule_data = {}

    for d in dates:
        daily_log = log_map.get(d)

        row = {
            'date': d,
            'day_name': d.strftime('%a'),
            'log': daily_log,
            'teacher_cells': []
        }

        row_sum = 0

        for t in teachers:
            sch = schedule_map.get((d, t.id))
            student_list = []
            if sch:
                student_list = list(sch.assigned_students.all())
                row_sum += len(student_list)

            # [핵심] 휴무 여부 판단: unavailable_set에 있는지 확인
            is_day_off = (d, t.id) in unavailable_set

            row['teacher_cells'].append({
                'teacher': t,
                'schedule': sch,
                'students': student_list,
                'is_off': is_day_off  # 템플릿에 전달
            })

        if daily_log:
            row_sum += daily_log.absent_students.count()
            row_sum += daily_log.exception_students.count()

        row['total_count'] = row_sum
        schedule_data[d] = row

    context = {
        'year': year,
        'month': month,
        'teachers': teachers,
        'schedule_data': schedule_data,
        'dates': dates,
        'all_students': all_students,
    }

    return render(request, 'schedule/monthly_grid.html', context)


@csrf_exempt
def save_monthly_schedule(request):
    """AJAX 저장 (휴무 정보는 TeacherUnavailable 모델에 저장)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            schedule_list = data.get('schedules', [])

            with transaction.atomic():
                for row in schedule_list:
                    date_str = row.get('date')

                    # 1. 교사별 데이터 처리
                    teachers_data = row.get('teachers', {})
                    for teacher_id, cell_data in teachers_data.items():
                        student_names_str = cell_data.get('text', '')
                        is_day_off = cell_data.get('is_off', False)
                        teacher = Teacher.objects.get(pk=teacher_id)

                        # A. 학생 배정 처리 (DailySchedule)
                        # 이름이 있을 때만 DailySchedule 생성/업데이트
                        if student_names_str.strip():
                            schedule, _ = DailySchedule.objects.get_or_create(
                                date=date_str,
                                teacher=teacher
                            )
                            names = [n.strip() for n in student_names_str.split(',') if n.strip()]
                            students_to_add = []
                            for name in names:
                                stu = Student.objects.filter(name=name, status='ATTENDING').first()
                                if stu: students_to_add.append(stu)
                            schedule.assigned_students.set(students_to_add)
                        else:
                            # 이름이 없으면 스케줄 객체가 굳이 필요 없을 수도 있지만,
                            # 기존에 있었다면 학생 명단을 비워줍니다.
                            schedule = DailySchedule.objects.filter(date=date_str, teacher=teacher).first()
                            if schedule:
                                schedule.assigned_students.clear()

                        # B. [핵심] 휴무 처리 (TeacherUnavailable)
                        if is_day_off:
                            # 휴무라면 레코드 생성 (없으면 만듦)
                            TeacherUnavailable.objects.get_or_create(
                                date=date_str,
                                teacher=teacher,
                                defaults={'reason': '스케줄표에서 설정'}
                            )
                        else:
                            # 휴무가 아니라면 기존 레코드 삭제 (있으면 지움)
                            TeacherUnavailable.objects.filter(
                                date=date_str,
                                teacher=teacher
                            ).delete()

                    # 2. 로그(근태) 저장
                    logs_data = row.get('logs', {})
                    daily_log, _ = DailyLog.objects.get_or_create(date=date_str)

                    def update_log_m2m(field_name, names_str):
                        names = [n.strip() for n in names_str.split(',') if n.strip()]
                        students = []
                        for name in names:
                            stu = Student.objects.filter(name=name).first()
                            if stu: students.append(stu)
                        getattr(daily_log, field_name).set(students)

                    update_log_m2m('absent_students', logs_data.get('absent', ''))
                    update_log_m2m('late_students', logs_data.get('late', ''))
                    update_log_m2m('exception_students', logs_data.get('exception', ''))

                    daily_log.remarks = logs_data.get('remarks', '')
                    daily_log.save()

            return JsonResponse({'status': 'success', 'message': '저장되었습니다.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)







# # schedule/views.py
#
# from django.shortcuts import render
# from django.utils import timezone
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.db import transaction
# import calendar
# import datetime
# import json
#
# from teachers.models import Teacher
# from students.models import Student
# from .models import DailySchedule, DailyLog
#
#
# def monthly_schedule(request):
#     """월간 스케줄 조회"""
#     # 1. 날짜 설정
#     today = timezone.localtime(timezone.now()).date()
#     year = int(request.GET.get('year', today.year))
#     month = int(request.GET.get('month', today.month))
#
#     # 2. 해당 월의 날짜 생성
#     _, last_day = calendar.monthrange(year, month)
#     dates = [datetime.date(year, month, day) for day in range(1, last_day + 1)]
#
#     # 3. [핵심] '재직(ACTIVE)' 상태인 교사만 가져오기
#     teachers = Teacher.objects.filter(status='ACTIVE').order_by('name')
#
#     # 재원생 목록 (자동완성용)
#     all_students = Student.objects.filter(status='ATTENDING').order_by('name')
#
#     # 4. 데이터 로드 (최적화)
#     schedules = DailySchedule.objects.filter(date__year=year, date__month=month).prefetch_related('assigned_students')
#     logs = DailyLog.objects.filter(date__year=year, date__month=month).prefetch_related('absent_students',
#                                                                                         'late_students',
#                                                                                         'exception_students')
#
#     schedule_map = {(s.date, s.teacher_id): s for s in schedules}
#     log_map = {l.date: l for l in logs}
#
#     schedule_data = {}
#
#     for d in dates:
#         # 날짜별 로그(근태) 가져오기
#         daily_log = log_map.get(d)
#
#         row = {
#             'date': d,
#             'day_name': d.strftime('%a'),
#             'log': daily_log,
#             'teacher_cells': []
#         }
#
#         row_sum = 0
#
#         # A. 교사별 배정 인원 합산
#         for t in teachers:
#             sch = schedule_map.get((d, t.id))
#             student_list = []
#             if sch:
#                 student_list = list(sch.assigned_students.all())
#                 row_sum += len(student_list)  # 교사 배정 인원 더하기
#
#             row['teacher_cells'].append({
#                 'teacher': t,
#                 'schedule': sch,
#                 'students': student_list,
#                 'is_off': sch.is_day_off if sch else False
#             })
#
#         # [핵심] B. 로그 합산 (지각 제외!)
#         if daily_log:
#             row_sum += daily_log.absent_students.count()  # 결석 포함
#             row_sum += daily_log.exception_students.count()  # 예외 포함
#             # row_sum += daily_log.late_students.count()     # [제외됨] 지각은 합계에 포함 안 함
#
#         row['total_count'] = row_sum
#         schedule_data[d] = row
#
#     context = {
#         'year': year,
#         'month': month,
#         'teachers': teachers,
#         'schedule_data': schedule_data,
#         'dates': dates,
#         'all_students': all_students,
#     }
#
#     return render(request, 'schedule/monthly_grid.html', context)
#
#
# @csrf_exempt
# def save_monthly_schedule(request):
#     """AJAX를 통한 월간 스케줄 일괄 저장"""
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             schedule_list = data.get('schedules', [])
#
#             with transaction.atomic():
#                 for row in schedule_list:
#                     date_str = row.get('date')
#
#                     # 1. 교사별 배정 저장
#                     teachers_data = row.get('teachers', {})
#                     for teacher_id, student_names_str in teachers_data.items():
#                         teacher = Teacher.objects.get(pk=teacher_id)
#
#                         schedule, created = DailySchedule.objects.get_or_create(
#                             date=date_str,
#                             teacher=teacher
#                         )
#
#                         # 쉼표로 구분된 이름 파싱
#                         names = [n.strip() for n in student_names_str.split(',') if n.strip()]
#                         students_to_add = []
#                         for name in names:
#                             stu = Student.objects.filter(name=name, status='ATTENDING').first()
#                             if stu: students_to_add.append(stu)
#
#                         schedule.assigned_students.set(students_to_add)
#
#                     # 2. 로그(근태) 저장
#                     logs_data = row.get('logs', {})
#                     daily_log, _ = DailyLog.objects.get_or_create(date=date_str)
#
#                     def update_log_m2m(field_name, names_str):
#                         names = [n.strip() for n in names_str.split(',') if n.strip()]
#                         students = []
#                         for name in names:
#                             stu = Student.objects.filter(name=name).first()
#                             if stu: students.append(stu)
#                         getattr(daily_log, field_name).set(students)
#
#                     update_log_m2m('absent_students', logs_data.get('absent', ''))
#                     update_log_m2m('late_students', logs_data.get('late', ''))
#                     update_log_m2m('exception_students', logs_data.get('exception', ''))
#
#                     daily_log.remarks = logs_data.get('remarks', '')
#                     daily_log.save()
#
#             return JsonResponse({'status': 'success', 'message': '저장되었습니다.'})
#
#         except Exception as e:
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
#
#     return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

