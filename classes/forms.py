# classes/forms.py

from django import forms
from .models import ClassInfo
from students.models import Student
from django.utils import timezone


class ClassForm(forms.ModelForm):
    # 수강생 추가 시 적용할 기준 날짜 (DB 저장 안 함, 계산용)
    enrollment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="수강 적용일 (청구 기준)",
        initial=timezone.localtime(timezone.now()).date,
        required=False,  # 수정 시에는 필수가 아닐 수도 있으므로
        help_text="* 신규 추가된 학생들에게 이 날짜를 기준으로 수강료가 일할 계산됩니다."
    )

    class Meta:
        model = ClassInfo
        fields = ['name', 'teacher', 'tuition_fee', 'schedule', 'enrollment_date', 'students', 'is_active',
                  'start_date', 'end_date']

        widgets = {
            'schedule': forms.HiddenInput(),  # 시간표 그리드용
            # students 위젯은 템플릿에서 수동으로 그릴 것이므로 여기서는 기본값 유지
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 학생 목록 정렬 (학년 -> 이름 순)
        self.fields['students'].queryset = Student.objects.all().order_by('grade', 'name')


# 수강 취소(퇴원) 날짜 선택 폼
class ClassDropForm(forms.Form):
    drop_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="퇴원일 (마지막 수업일)",
        initial=timezone.localtime(timezone.now()).date
    )

