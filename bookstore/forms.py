# bookstore/forms.py

from django import forms
from .models import Book, BookStockLog, BookSupplier, BookSale
import re


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['created_at', 'title', 'isbn', 'author', 'publisher', 'supplier', 'original_price',
                  'cost_price', 'price', 'stock', 'memo']
        widgets = {
            'created_at': forms.DateInput(attrs={'type': 'date'}),
            'isbn': forms.TextInput(attrs={
                'placeholder': '바코드를 스캔하세요',
                'autofocus': 'autofocus',
                'class': 'ime-mode-disabled',
                'id': 'id_isbn',  # ID 명시
            }),
            # 구매처 선택 위젯
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'original_price': forms.NumberInput(attrs={'step': '100'}),
            'cost_price': forms.NumberInput(attrs={'step': '10'}),
            'price': forms.NumberInput(attrs={'step': '100'}),
            'memo': forms.TextInput(attrs={'placeholder': '비고 (선택 사항)'}),
        }

    def clean_isbn(self):
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            # 1. 숫자와 'X'만 남기고 모두 제거 (하이픈 등 제거)
            isbn = re.sub(r'[^0-9X]', '', isbn.upper())

            # 2. ISBN-10 (10자리) -> ISBN-13 (13자리) 변환 로직
            if len(isbn) == 10:
                # 2-1. 앞 9자리만 추출
                core = isbn[:9]
                # 2-2. 978 접두어 추가
                temp_isbn = "978" + core

                # 2-3. 체크 디짓(Check Digit) 계산
                # (홀수자리 합) + (짝수자리 합 * 3)
                total = 0
                for i, digit in enumerate(temp_isbn):
                    total += int(digit) * (1 if i % 2 == 0 else 3)

                check_digit = (10 - (total % 10)) % 10

                # 2-4. 최종 13자리 완성
                isbn = temp_isbn + str(check_digit)

            # 3. 길이 재검사 (이제 무조건 13자리여야 함)
            if len(isbn) != 13:
                raise forms.ValidationError(f"올바르지 않은 바코드 길이입니다. (변환 후 {len(isbn)}자리)")

        return isbn


# 구매처 등록 폼
class BookSupplierForm(forms.ModelForm):
    class Meta:
        model = BookSupplier
        fields = ['name', 'registration_number', 'phone', 'address', 'bank_name', 'account_number', 'account_owner']
        widgets = {
            'address': forms.TextInput(attrs={'placeholder': '주소 입력'}),
        }


class BookStockLogForm(forms.ModelForm):
    class Meta:
        model = BookStockLog
        fields = ['created_at', 'supplier', 'quantity', 'cost_price', 'memo']

        widgets = {
            'created_at': forms.DateInput(attrs={'type': 'date'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'autofocus': 'autofocus'}),
            'cost_price': forms.NumberInput(attrs={'step': 100}),
            'memo': forms.TextInput(attrs={'placeholder': '비고'}),
        }
        labels = {
            'created_at': '입고 날짜',  # 라벨 이름 지정
        }

# 반품 전용 폼 (환불 날짜와 금액 포함)
class BookReturnForm(forms.ModelForm):
    class Meta:
        model = BookStockLog
        fields = ['supplier', 'quantity', 'cost_price', 'total_payment', 'payment_date', 'memo']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'autofocus': 'autofocus'}),
            'cost_price': forms.NumberInput(attrs={'step': 100}),
            # 총액은 읽기 전용 (JS로 자동 계산)
            'total_payment': forms.NumberInput(attrs={'readonly': 'readonly', 'style': 'background-color: #eee;'}),
            # 날짜 입력 위젯
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'memo': forms.TextInput(attrs={'placeholder': '반품 사유'}),
        }


# 교재 판매(분배) 폼
class BookSaleForm(forms.ModelForm):
    class Meta:
        model = BookSale
        fields = ['sale_date', 'book', 'quantity', 'price', 'is_paid', 'memo']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'value': 1}),
            'price': forms.NumberInput(attrs={'step': 100}),
            'sale_date': forms.DateInput(attrs={'type': 'date'}),
            'memo': forms.TextInput(attrs={'placeholder': '비고'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 재고가 1권 이상인 책만 표시 & 이름순 정렬
        self.fields['book'].queryset = Book.objects.filter(stock__gt=0).order_by('title')
        self.fields['book'].label = "판매할 교재"