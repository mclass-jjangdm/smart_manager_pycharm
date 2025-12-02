# schedule/models.py

from django.db import models
from teachers.models import Teacher
from students.models import Student


class DailySchedule(models.Model):
    """특정 날짜, 특정 교사의 수업 배정 정보"""
    date = models.DateField(verbose_name="날짜")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='daily_schedules', verbose_name="담당 교사")

    # 배정된 학생들
    assigned_students = models.ManyToManyField(Student, blank=True, related_name='daily_assigned', verbose_name="배정 학생")

    class Meta:
        unique_together = ('date', 'teacher')  # 같은 날, 같은 교사 중복 방지


class DailyLog(models.Model):
    """날짜별 특이사항 및 근태 관리 (행 단위 데이터)"""
    date = models.DateField(unique=True, verbose_name="날짜")

    # 결석/지각/예외 학생들은 텍스트로 관리하거나 M2M으로 할 수 있으나, 
    # 스프레드시트 입력을 위해 일단 유연하게 M2M으로 갑니다.
    absent_students = models.ManyToManyField(Student, blank=True, related_name='daily_absent', verbose_name="결석생")
    late_students = models.ManyToManyField(Student, blank=True, related_name='daily_late', verbose_name="지각생")
    exception_students = models.ManyToManyField(Student, blank=True, related_name='daily_exception', verbose_name="예외생")
    remarks = models.TextField(blank=True, verbose_name="특이사항")

    def __str__(self):
        return str(self.date)

