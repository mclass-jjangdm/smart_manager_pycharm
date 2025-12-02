# teachers/models.py

from django.db import models
from django.utils import timezone
import datetime


class Teacher(models.Model):
    # [추가] 교사 상태 선택지
    STATUS_CHOICES = [
        ('ACTIVE', '재직'),
        ('RESIGNED', '퇴직'),
        ('LEAVE', '휴직'),
    ]
    """교사 기본 정보 모델"""
    name = models.CharField(max_length=100, verbose_name="이름")
    gender = models.CharField(max_length=10, choices=[('M', '남'), ('F', '여')], verbose_name="성별")
    phone = models.CharField(max_length=20, verbose_name="전화번호")
    email = models.EmailField(blank=True, null=True, verbose_name="이메일")

    # 근무 정보
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE', verbose_name="상태")
    hire_date = models.DateField(verbose_name="입사일", default=timezone.now)
    resign_date = models.DateField(blank=True, null=True, verbose_name="퇴사일")

    # 급여 정보 (원 단위)
    base_pay = models.PositiveIntegerField(default=0, verbose_name="급여 기준(시급/건별)")
    extra_pay = models.PositiveIntegerField(default=0, verbose_name="추가 급여")

    # 계좌 정보
    bank_name = models.CharField(max_length=50, verbose_name="거래은행")
    account_number = models.CharField(max_length=50, verbose_name="급여계좌번호")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "교사"
        verbose_name_plural = "교사 목록"


class TeacherWorkRecord(models.Model):
    """교사 근무 기록 모델"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="work_records", verbose_name="교사")
    date = models.DateField(verbose_name="근무 날짜", default=timezone.now)

    # 기본값: 오후 6시 ~ 오후 8시 (요구사항 반영)
    start_time = models.TimeField(verbose_name="시작 시간", default=datetime.time(18, 0))
    end_time = models.TimeField(verbose_name="종료 시간", default=datetime.time(20, 0))

    # 실제 근무 시간 (분 단위 혹은 시간 단위로 계산하여 저장할 수도 있지만, 시작/종료 시간으로 계산 가능)

    memo = models.CharField(max_length=200, blank=True, null=True, verbose_name="비고")

    def get_work_hours(self):
        """근무 시간 계산 (시간 단위, 소수점 포함)"""
        # 날짜를 임의로 결합하여 시간 차이 계산
        dummy_date = datetime.date(2000, 1, 1)
        start = datetime.datetime.combine(dummy_date, self.start_time)
        end = datetime.datetime.combine(dummy_date, self.end_time)

        # 종료 시간이 시작 시간보다 빠르면 다음날로 간주 (야간 근무 등)
        if end < start:
            end += datetime.timedelta(days=1)

        diff = end - start
        return round(diff.total_seconds() / 3600, 2)  # 시간을 소수점 2자리까지 반환

    def __str__(self):
        return f"{self.teacher.name} - {self.date} ({self.start_time}~{self.end_time})"

    class Meta:
        verbose_name = "근무 기록"
        verbose_name_plural = "근무 기록 목록"
        ordering = ['-date']  # 최신 날짜 순 정렬


class TeacherUnavailable(models.Model):
    """근무 불가능한 날짜 관리"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="unavailable_dates", verbose_name="교사")
    date = models.DateField(verbose_name="근무 불가 날짜")
    reason = models.CharField(max_length=200, blank=True, null=True, verbose_name="사유")

    def __str__(self):
        return f"{self.teacher.name} - {self.date} (불가)"

    class Meta:
        verbose_name = "근무 불가 일정"
        verbose_name_plural = "근무 불가 일정 목록"


class TeacherPaymentRecord(models.Model):
    """교사 급여 지급 내역 기록 모델"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='payments', verbose_name="교사")
    year = models.IntegerField(verbose_name="년도")
    month = models.IntegerField(verbose_name="월")
    amount_paid = models.PositiveIntegerField(verbose_name="실제 지급액")
    payment_date = models.DateField(default=timezone.now, verbose_name="지급일")
    is_paid = models.BooleanField(default=True, verbose_name="지급 완료 여부")

    class Meta:
        # 특정 교사의 특정 월에 대한 지급 기록은 하나만 존재해야 합니다. (중복 방지)
        unique_together = ('teacher', 'year', 'month')
        verbose_name = "급여 지급 기록"
        verbose_name_plural = "급여 지급 기록"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.teacher.name} - {self.year}-{self.month} ({'지급 완료' if self.is_paid else '미지급'})"