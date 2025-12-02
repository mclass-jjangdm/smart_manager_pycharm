# students/forms.py

from django import forms
from .models import Student, StudentFile
from classes.models import ClassInfo # 수업 모델 임포트
from django.utils import timezone


# 다중 파일 업로드를 지원하는 커스텀 위젯 정의
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class StudentForm(forms.ModelForm):
    """학생 등록을 위한 모델 폼"""

    class Meta:
        model = Student  # Student 모델을 기반으로 폼을 만듭니다.

        # 폼에 표시할 필드들
        fields = [
            'name', 'school', 'grade', 'student_phone', 'email', 'gender',
            'parent_phone', 'receipt_phone', 'interview_date',
            'interview_score', 'interview_info', 'first_class_date',
            'last_class_date', 'misc', 'status',
        ]

        # HTML 폼 위젯 설정 (예: 날짜 필드를 'date' 타입으로)
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select', 'style': 'font-weight: bold;'}),
            'interview_date': forms.DateInput(attrs={'type': 'date'}),
            'first_class_date': forms.DateInput(attrs={'type': 'date'}),
            'last_class_date': forms.DateInput(attrs={'type': 'date'}),
            'interview_info': forms.Textarea(attrs={'rows': 3}),
            'misc': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        """폼 초기화 시 '이름' 필드를 필수로 설정"""
        super().__init__(*args, **kwargs)
        # '이름' 필드는 필수 입력 항목으로 설정
        self.fields['name'].required = True
        # '학년' 필드도 필수 입력 항목으로 설정
        self.fields['grade'].required = True
        # '성별' 필드도 필수 입력 항목으로 설정
        self.fields['gender'].required = True


# 학생 파일 업로드를 위한 폼
class StudentFileForm(forms.ModelForm):
    """학생 파일 업로드 폼"""
    class Meta:
        model = StudentFile
        # [주석] 파일과 설명만 입력받습니다. (student는 뷰에서 설정)
        fields = ['file', 'description']
        widgets = {
            'file': MultipleFileInput(attrs={'multiple': True}),
            'description': forms.TextInput(attrs={'placeholder': '파일 설명 (선택)'}),
        }


class SMSForm(forms.Form):
    TARGET_CHOICES = [
        ('student', '학생 본인'),
        ('parent', '학부모님'),
        ('both', '학생 + 학부모님 (동시 발송)'),
    ]

    target = forms.ChoiceField(choices=TARGET_CHOICES, label="수신 대상", widget=forms.RadioSelect)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'placeholder': '내용을 입력하세요'}), label="문자 내용")


# 학생 수강 신청 폼
class StudentClassForm(forms.Form):
    # 수강 시작일 선택 필드
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="수강 시작일",
        initial=timezone.localtime(timezone.now()).date
    )
    classes = forms.ModelMultipleChoiceField(
        queryset=ClassInfo.objects.filter(is_active=True).order_by('name'), # 진행 중인 수업만 표시
        widget=forms.CheckboxSelectMultiple,
        label="수강할 강좌 선택"
    )


