# classes/models.py

from django.db import models
from teachers.models import Teacher
from students.models import Student
from django.utils import timezone


class ClassInfo(models.Model):
    """수업(강좌) 정보 모델"""
    name = models.CharField(max_length=100, verbose_name="수업명")

    # 담당 교사 (한 수업에 선생님은 한 명이라고 가정, 필요하면 ManyToMany로 변경 가능)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="담당 교사")

    # 수강 학생들 (다대다 관계: 한 학생이 여러 수업, 한 수업에 여러 학생)
    students = models.ManyToManyField(Student, related_name='enrolled_classes', blank=True, verbose_name="수강생 목록")

    # 수업료 (이게 있어야 나중에 자동 청구가 됩니다)
    tuition_fee = models.PositiveIntegerField(default=0, verbose_name="수강료(월)")

    # 수업 일정 (예: 월수금 18:00) - 일단 단순 텍스트로 관리
    schedule = models.CharField(max_length=500, blank=True, null=True, verbose_name="수업 시간")

    # 개강일/종강일 (선택 사항)
    start_date = models.DateField(blank=True, null=True, verbose_name="개강일")
    end_date = models.DateField(blank=True, null=True, verbose_name="종강일")

    is_active = models.BooleanField(default=True, verbose_name="진행 중 여부")

    created_at = models.DateTimeField(auto_now_add=True)

    # [추가] 스케줄 데이터를 보기 좋게 변환하는 함수
    def get_formatted_schedule(self):
        if not self.schedule:
            return "-"

        # 1. 데이터 파싱 (예: "월-14,월-15,수-10" -> {'월': [14, 15], '수': [10]})
        slots = {}
        try:
            for item in self.schedule.split(','):
                if '-' in item:
                    day, hour = item.split('-')
                    if day not in slots: slots[day] = []
                    slots[day].append(int(hour))
        except:
            return self.schedule  # 파싱 에러 시 원본 반환

        # 2. 요일 순서대로 정렬 및 시간대 병합
        days_order = ['월', '화', '수', '목', '금', '토', '일']
        result_parts = []

        for day in days_order:
            if day in slots:
                hours = sorted(slots[day])
                if not hours: continue

                # 연속된 시간 찾기 알고리즘
                ranges = []
                start = hours[0]
                end = hours[0]

                for i in range(1, len(hours)):
                    if hours[i] == end + 1:  # 연속된 시간이면 끝시간 연장
                        end = hours[i]
                    else:  # 끊기면 지금까지를 저장하고 새로 시작
                        ranges.append(f"{start}:00~{end + 1}:00")
                        start = hours[i]
                        end = hours[i]

                # 마지막 남은 범위 저장 (end+1을 해서 종료 시간을 표시)
                ranges.append(f"{start}:00~{end + 1}:00")

                # 예: "수 20:00~22:00"
                result_parts.append(f"{day} {', '.join(ranges)}")

        return " / ".join(result_parts)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "수업"
        verbose_name_plural = "수업 목록"
        ordering = ['-is_active', 'name']


# 수강료 청구/납부 기록 모델
class TuitionLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='tuition_logs', verbose_name="학생")
    class_info = models.ForeignKey(ClassInfo, on_delete=models.PROTECT, related_name='logs', verbose_name="수업")

    charge_date = models.DateField(default=timezone.now, verbose_name="청구일")
    amount = models.PositiveIntegerField(verbose_name="청구 금액")
    month = models.CharField(max_length=20, verbose_name="해당 월", blank=True)  # 예: "11월 수강료"

    is_paid = models.BooleanField(default=False, verbose_name="납부 여부")
    payment_date = models.DateField(blank=True, null=True, verbose_name="납부일")

    memo = models.CharField(max_length=255, blank=True, null=True, verbose_name="비고")

    def __str__(self):
        return f"{self.student.name} - {self.class_info.name} ({self.amount})"

    class Meta:
        verbose_name = "수강료 내역"
        verbose_name_plural = "수강료 내역"
        ordering = ['-charge_date']

