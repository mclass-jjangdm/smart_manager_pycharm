# bookstore/models.py

from django.db import models
from django.utils import timezone
from students.models import Student


class BookSupplier(models.Model):
    """도서 구매처(출판사/서점) 정보"""
    name = models.CharField(max_length=100, verbose_name="상호명(법인명)")
    registration_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="사업자 등록번호")
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="전화번호")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="주소")

    # 계좌 정보
    bank_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="은행명")
    account_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="계좌번호")
    account_owner = models.CharField(max_length=50, blank=True, null=True, verbose_name="예금주")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="등록일")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "구매처"
        verbose_name_plural = "구매처 목록"


class Book(models.Model):
    """교재(상품) 기본 정보 모델"""
    title = models.CharField(max_length=200, verbose_name="교재명")
    isbn = models.CharField(max_length=50, unique=True, verbose_name="바코드(ISBN)")
    author = models.CharField(max_length=100, blank=True, null=True, verbose_name="저자")
    publisher = models.CharField(max_length=100, blank=True, null=True, verbose_name="출판사")
    supplier = models.ForeignKey('BookSupplier', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="주거래 구매처")
    original_price = models.PositiveIntegerField(default=0, verbose_name="정상 가격")  # 정가
    cost_price = models.PositiveIntegerField(default=0, verbose_name="입고 가격")  # 원가
    price = models.PositiveIntegerField(default=0, verbose_name="판매 가격")
    stock = models.PositiveIntegerField(default=0, verbose_name="재고 수량")
    memo = models.TextField(blank=True, null=True, verbose_name="비고")

    created_at = models.DateTimeField(default=timezone.now, verbose_name="등록일(입고일)")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "교재"
        verbose_name_plural = "교재 목록"
        ordering = ['title']


class BookSale(models.Model):
    """교재 판매/분배 내역 모델"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='book_sales', verbose_name="학생")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='sales', verbose_name="교재")

    sale_date = models.DateField(default=timezone.now, verbose_name="판매일(지급일)")
    price = models.PositiveIntegerField(verbose_name="판매 당시 가격")  # 가격 변동 대비
    quantity = models.PositiveIntegerField(default=1, verbose_name="수량")

    is_paid = models.BooleanField(default=False, verbose_name="결제 완료 여부")
    payment_date = models.DateField(blank=True, null=True, verbose_name="결제일")

    memo = models.CharField(max_length=255, blank=True, null=True, verbose_name="비고")

    def get_total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.student.name} - {self.book.title}"

    class Meta:
        verbose_name = "교재 판매 내역"
        verbose_name_plural = "교재 판매 내역"
        ordering = ['-sale_date']


class BookStockLog(models.Model):
    """교재 입고(재고 추가) 및 반품 기록"""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='stock_logs', verbose_name="교재")
    # 구매처 연결(Optional: 기존 데이터 호환성을 위해 null = True)
    supplier = models.ForeignKey(BookSupplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="구매처")
    # PositiveIntegerField -> IntegerField (반품 시 -수량 저장을 위해)
    quantity = models.IntegerField(verbose_name="수량 (입고/반품)")
    cost_price = models.PositiveIntegerField(verbose_name="단가")
    total_payment = models.PositiveIntegerField(default=0, verbose_name="총액")
    payment_date = models.DateField(blank=True, null=True, verbose_name="날짜")  # 지급일 or 반품일
    # auto_now_add=True를 삭제하고 default=timezone.now 로 변경
    created_at = models.DateTimeField(default=timezone.now, verbose_name="입고/반품일")
    memo = models.CharField(max_length=255, blank=True, null=True, verbose_name="비고")
    # 정산(입금) 완료 여부
    is_paid = models.BooleanField(default=False, verbose_name="정산 완료 여부")

    def save(self, *args, **kwargs):
        # 총액 자동 계산 (절대값 사용)
        if not self.total_payment:
            self.total_payment = abs(self.quantity * self.cost_price)

        if not self.pk:
            # 수량만큼 재고 변경 (음수면 재고 감소)
            self.book.stock += self.quantity

            # 입고(양수)일 때만 단가 업데이트
            if self.quantity > 0:
                self.book.cost_price = self.cost_price

            self.book.save()
        super().save(*args, **kwargs)

    def __str__(self):
        action = "입고" if self.quantity > 0 else "반품"
        return f"{self.book.title} ({action} {abs(self.quantity)})"

    class Meta:
        verbose_name = "재고 기록"
        verbose_name_plural = "재고 기록"
        ordering = ['-created_at']

