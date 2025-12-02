# students/models.py

import os
import random
from django.db import models
from django.utils import timezone


# 학년 선택지 (K5 ~ K12)
GRADE_CHOICES = [(f'K{i}', f'K{i}') for i in range(5, 13)]


def student_file_upload_path(instance, filename):
    """
    학생 개별 파일 업로드 경로를 생성합니다.
    예: media/students/STUDENT_ID/filename.pdf
    """
    # instance.student.id는 이 파일이 속한 학생의 고유 ID입니다.
    return f'students/{instance.student.id}/{filename}'


def generate_student_number():
    """
    0으로 시작하지 않는 8자리 고유 번호(10000000 ~ 99999999)를 생성합니다.
    중복된 번호가 있으면 다시 생성합니다.
    """
    while True:
        number = random.randint(10000000, 99999999)
        # 이미 존재하는 번호인지 확인 (Student 모델이 정의되기 전이라 클래스 내부에서 호출될 때 처리)
        if not Student.objects.filter(student_number=number).exists():
            return number


class Student(models.Model):
    """학생 기본 정보 모델"""
    # 8자리 고유 번호 (외부 노출용)
    # unique=True: 중복 방지
    # editable=False: 관리자가 수정하지 못하게 함 (자동 생성)
    student_number = models.PositiveIntegerField(
        unique=True,
        default=generate_student_number,
        editable=False,
        verbose_name="학생 고유 번호"
    )
    # 기본 정보
    name = models.CharField(max_length=100, verbose_name="이름")
    school = models.CharField(max_length=100, blank=True, null=True, verbose_name="학교")
    grade = models.CharField(max_length=3, choices=GRADE_CHOICES, verbose_name="학년")
    student_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="학생 전화번호")
    email = models.EmailField(blank=True, null=True, verbose_name="이메일 주소")
    gender = models.CharField(max_length=10, choices=[('M', '남'), ('F', '여')], verbose_name="성별")
    parent_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="부모님 전화번호")
    receipt_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="현금 영수증 용 번호")

    # 인터뷰 정보
    interview_date = models.DateField(blank=True, null=True, verbose_name="인터뷰 날짜")
    interview_score = models.CharField(max_length=50, blank=True, null=True, verbose_name="인터뷰 기본 성적")
    interview_info = models.TextField(blank=True, null=True, verbose_name="인터뷰 정보")

    # 수업 정보
    first_class_date = models.DateField(blank=True, null=True, verbose_name="첫 수업 날짜")
    last_class_date = models.DateField(blank=True, null=True, verbose_name="그만 둔 날짜")

    # 기타
    misc = models.TextField(blank=True, null=True, verbose_name="기타")

    # 등록일 (관리용)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    # 미납 수업료/교재비 총액
    unpaid_amount = models.IntegerField(default=0, verbose_name="미납 총액")

    # 재원 상태 선택지
    STATUS_CHOICES = [
        ('ATTENDING', '재원 (다니는 중)'),
        ('BREAK', '휴원 (잠시 쉼)'),
        ('DISCHARGED', '퇴원 (그만둠)'),
        ('GRADUATED', '졸업'),
    ]
    # 상태 필드 (기본값: 재원)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATTENDING', verbose_name="재원 상태")

    def __str__(self):
        # 관리자 페이지 등에서 고유 번호도 같이 보이게 수정
        return f"[{self.student_number}] {self.name} ({self.grade})"

    class Meta:
        verbose_name = "학생"
        verbose_name_plural = "학생 목록"


class StudentFile(models.Model):
    """학생 개별 파일 관리 모델"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="files", verbose_name="학생")
    file = models.FileField(upload_to=student_file_upload_path, verbose_name="첨부 파일")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="파일 설명")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="업로드 날짜")

    def __str__(self):
        # 파일명만 반환
        return os.path.basename(self.file.name)

    class Meta:
        verbose_name = "학생 파일"
        verbose_name_plural = "학생 파일 목록"


class StudentSchedule(models.Model):
    """개인별 특별 학생 일정"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="schedules", verbose_name="학생")
    title = models.CharField(max_length=200, verbose_name="일정 제목")
    description = models.TextField(blank=True, null=True, verbose_name="일정 내용")
    schedule_date = models.DateField(verbose_name="일정 날짜")
    start_time = models.TimeField(blank=True, null=True, verbose_name="시작 시간")
    end_time = models.TimeField(blank=True, null=True, verbose_name="종료 시간")

    def __str__(self):
        return f"{self.student.name} - {self.title} ({self.schedule_date})"

    class Meta:
        verbose_name = "학생 개별 일정"
        verbose_name_plural = "학생 개별 일정 목록"