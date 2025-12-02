# teachers/forms.py

from django import forms
from .models import Teacher, TeacherWorkRecord, TeacherUnavailable

class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = [
            'name', 'gender', 'phone', 'email',
            'hire_date', 'resign_date', 'status',
            'base_pay', 'extra_pay',
            'bank_name', 'account_number'
        ]
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'resign_date': forms.DateInput(attrs={'type': 'date'}),
        }

class WorkRecordForm(forms.ModelForm):
    """근무 기록 입력 폼"""
    class Meta:
        model = TeacherWorkRecord
        fields = ['date', 'start_time', 'end_time', 'memo']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            # format='%H:%M'을 추가하여 24시간제 값(18:00)으로 HTML에 전달되도록 함
            'start_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '300'}),
            'end_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '300'}),
            'memo': forms.TextInput(attrs={'placeholder': '특이사항 (선택)'}),
        }

class UnavailableForm(forms.ModelForm):
    """근무 불가 일정 입력 폼"""
    class Meta:
        model = TeacherUnavailable
        fields = ['date', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.TextInput(attrs={'placeholder': '사유 (예: 개인 사정)'}),
        }
