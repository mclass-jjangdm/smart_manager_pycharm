# bookstore/views.py

from django.shortcuts import render, redirect, get_object_or_404
from .models import Book, BookStockLog, BookSupplier, BookSale
from .forms import BookForm, BookStockLogForm, BookSupplierForm, BookReturnForm, BookSaleForm
from django.db.models import Q
from django.contrib import messages
import pandas as pd # 엑셀 처리를 위해 필수
import re # ISBN 정리를 위해 필요
from django.utils import timezone
import requests # 외부 API 호출용
from django.http import JsonResponse # JSON 응답용
import urllib3 # SSL 경고 숨기기용
from django.db import transaction # 트랜잭션 필수
from students.models import Student # 학생 모델 참조 필요
from django.core.paginator import Paginator


# SSL 인증서 경고 무시 설정 (터미널이 지저분해지는 것 방지)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def book_list(request):
    """교재 목록 조회 (검색 실패 시 자동 이동 플래그 처리)"""
    query = request.GET.get('q', '')

    # 기본 정렬: 최신순
    books = Book.objects.all().order_by('-created_at')

    is_search_empty = False  # 검색 결과 없음 플래그

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(isbn__icontains=query) |
            Q(author__icontains=query)
        )
        # 검색어는 있는데 결과가 0개인 경우 -> 자동 이동 트리거
        if not books.exists():
            is_search_empty = True

    paginator = Paginator(books, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'bookstore/book_list.html', {
        'page_obj': page_obj,
        'query': query,
        'is_search_empty': is_search_empty,
    })


def book_create(request):
    """신규 교재 입고 (데이터 유지 기능 강화)"""
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            initial_stock = book.stock
            book.stock = 0
            book.save()

            if initial_stock > 0:
                BookStockLog.objects.create(
                    book=book,
                    supplier=book.supplier,
                    quantity=initial_stock,
                    cost_price=book.cost_price,
                    created_at=book.created_at,
                    memo="신규 도서 등록 (초기 재고)"
                )
            messages.success(request, f"'{book.title}' 도서가 등록되었습니다.")
            return redirect('book_list')
    else:
        # [핵심] URL 파라미터(?isbn=...&title=...)를 폼 초기값으로 설정
        initial_data = {
            'created_at': timezone.localtime(timezone.now()).date(),
            'isbn': request.GET.get('isbn', ''),
            'title': request.GET.get('title', ''),
            'author': request.GET.get('author', ''),
            'publisher': request.GET.get('publisher', ''),
            'original_price': request.GET.get('original_price', ''),
            'cost_price': request.GET.get('cost_price', ''),
            'price': request.GET.get('price', ''),
            'stock': request.GET.get('stock', ''),
            'memo': request.GET.get('memo', ''),
        }

        # supplier_id가 넘어왔다면 처리
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            try:
                initial_data['supplier'] = int(supplier_id)
            except ValueError:
                pass

        form = BookForm(initial=initial_data)

    return render(request, 'bookstore/book_form.html', {'form': form, 'title': '📚 신규 교재 등록'})


def book_update(request, pk):
    """교재 정보 수정"""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            return redirect('book_list')
    else:
        form = BookForm(instance=book)

    return render(request, 'bookstore/book_form.html', {'form': form, 'title': f'📚 교재 정보 수정: {book.title}'})


def book_delete(request, pk):
    """도서 삭제"""
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        book.delete()
        return redirect('book_list')

    # GET 요청 시에는 그냥 목록으로 (혹은 삭제 확인 페이지)
    return redirect('book_list')


def book_restock(request, pk):
    """기존 교재 추가 입고 (재고 증가)"""
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        form = BookStockLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.book = book
            log.save()  # 모델 save()에서 재고 증가 및 총액 계산

            messages.success(request, f"'{book.title}' {log.quantity}권이 입고되었습니다.")
            return redirect('book_list')
    else:
        # 오늘 날짜를 기본 지급일로 설정
        form = BookStockLogForm(initial={
            'cost_price': book.cost_price,
            'payment_date': timezone.now().date()
        })

    recent_logs = book.stock_logs.all()[:5]

    return render(request, 'bookstore/book_restock.html', {
        'form': form,
        'book': book,
        'recent_logs': recent_logs
    })


def book_detail(request, pk):
    """도서 상세 정보 및 입고 이력 조회"""
    book = get_object_or_404(Book, pk=pk)

    # 해당 도서의 모든 입고 기록을 최신순으로 조회
    stock_logs = book.stock_logs.all().order_by('-created_at')

    return render(request, 'bookstore/book_detail.html', {
        'book': book,
        'stock_logs': stock_logs
    })


def book_return(request, pk):
    """교재 반품 처리 (재고 감소)"""
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        form = BookReturnForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.quantity = -abs(log.quantity)  # 음수 변환
            log.book = book
            log.save()
            messages.warning(request, f"'{book.title}' {abs(log.quantity)}권이 반품 처리되었습니다. (현재 재고: {book.stock}권)")
            return redirect('book_list')
    else:
        form = BookReturnForm(initial={
            'cost_price': book.cost_price,

            # [핵심 수정] UTC 시간을 한국 시간(Local Time)으로 변환 후 날짜 추출
            'payment_date': timezone.localtime(timezone.now()).date(),

            'memo': '재고 반품'
        })

    recent_logs = book.stock_logs.all()[:5]

    return render(request, 'bookstore/book_return.html', {
        'form': form,
        'book': book,
        'recent_logs': recent_logs
    })


def book_upload(request):
    """엑셀/CSV 파일로 도서 일괄 등록"""
    if request.method == 'POST' and request.FILES.get('upload_file'):
        upload_file = request.FILES['upload_file']

        try:
            if upload_file.name.endswith('.csv'):
                df = pd.read_csv(upload_file)
            else:
                df = pd.read_excel(upload_file)

            success_count = 0
            skip_count = 0

            for index, row in df.iterrows():
                # 1. 필수값(ISBN, 교재명) 확인
                title = row.get('교재명')
                raw_isbn = str(row.get('ISBN', '')).strip()

                if pd.isna(title) or not raw_isbn:
                    continue

                # 2. ISBN 정리 (하이픈 제거 및 13자리 변환 로직 간소화)
                # (여기서는 간단히 숫자와 X만 남기는 정리만 수행합니다)
                isbn = re.sub(r'[^0-9X]', '', raw_isbn.upper())

                # 3. 중복 확인 (이미 등록된 ISBN이면 건너뜀)
                if Book.objects.filter(isbn=isbn).exists():
                    skip_count += 1
                    continue

                # 4. 데이터 추출 및 저장
                Book.objects.create(
                    title=title,
                    isbn=isbn,
                    author=row.get('저자', ''),
                    publisher=row.get('출판사', ''),
                    # 가격 정보 (값이 없으면 0으로 처리)
                    original_price=pd.to_numeric(row.get('정상가격'), errors='coerce') or 0,
                    cost_price=pd.to_numeric(row.get('입고가격'), errors='coerce') or 0,
                    price=pd.to_numeric(row.get('판매가격'), errors='coerce') or 0,
                    stock=pd.to_numeric(row.get('재고'), errors='coerce') or 0,
                )
                success_count += 1

            messages.success(request, f"{success_count}권의 도서가 등록되었습니다. (중복 제외: {skip_count}권)")
            return redirect('book_list')

        except Exception as e:
            messages.error(request, f"파일 업로드 중 오류가 발생했습니다: {e}")
            return redirect('book_upload')

    return render(request, 'bookstore/book_upload.html')


def supplier_list(request):
    """구매처 목록 조회"""
    suppliers = BookSupplier.objects.all().order_by('name')
    return render(request, 'bookstore/supplier_list.html', {'suppliers': suppliers})


def supplier_create(request):
    """새로운 도서 공급처 등록 (등록 후 이전 페이지로 복귀 기능 추가)"""

    # [핵심] URL에 '?next=...'가 있는지 확인 (있다면 그 주소를 저장)
    next_url = request.GET.get('next')

    if request.method == 'POST':
        form = BookSupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f"구매처 '{supplier.name}' 등록이 완료되었습니다.")

            # [핵심] 돌아갈 주소가 있다면 거기로 리다이렉트
            if next_url:
                return redirect(next_url)

            # 없으면 원래대로 목록으로 이동
            return redirect('supplier_list')
    else:
        form = BookSupplierForm()

    return render(request, 'bookstore/supplier_form.html', {
        'form': form,
        'title': '🏢 새 구매처 등록'
    })


def supplier_update(request, pk):
    """구매처 정보 수정"""
    supplier = get_object_or_404(BookSupplier, pk=pk)
    if request.method == 'POST':
        form = BookSupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            return redirect('supplier_list')
    else:
        form = BookSupplierForm(instance=supplier)

    return render(request, 'bookstore/supplier_form.html', {'form': form, 'title': f'🏢 구매처 수정: {supplier.name}'})


def supplier_delete(request, pk):
    """구매처 삭제"""
    supplier = get_object_or_404(BookSupplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, "구매처 정보가 삭제되었습니다.")
        return redirect('supplier_list')
    return redirect('supplier_list')


def supplier_detail(request, pk):
    """구매처 상세: 지급 대상과 환불 대상을 분리하여 조회"""
    supplier = get_object_or_404(BookSupplier, pk=pk)

    # 1. 지급 대상 (입고: quantity > 0) 이면서 미정산
    unpaid_restocks = BookStockLog.objects.filter(
        supplier=supplier,
        is_paid=False,
        quantity__gt=0
    ).order_by('-created_at')

    # 2. 환불/차감 대상 (반품: quantity < 0) 이면서 미정산
    unpaid_returns = BookStockLog.objects.filter(
        supplier=supplier,
        is_paid=False,
        quantity__lt=0
    ).order_by('-created_at')

    # 지급 완료 내역
    paid_logs = BookStockLog.objects.filter(
        supplier=supplier,
        is_paid=True
    ).order_by('-payment_date', '-created_at')

    # 총액 계산 (각각 계산)
    total_to_pay = sum(log.total_payment for log in unpaid_restocks)
    total_to_refund = sum(log.total_payment for log in unpaid_returns)  # 반품액 합계

    return render(request, 'bookstore/supplier_detail.html', {
        'supplier': supplier,
        'unpaid_restocks': unpaid_restocks,  # 변경
        'unpaid_returns': unpaid_returns,  # 변경
        'paid_logs': paid_logs,
        'total_to_pay': total_to_pay,  # 변경
        'total_to_refund': total_to_refund,  # 변경
        'today': timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
    })


# 지급 취소(정산 취소) 뷰
def supplier_payment_cancel(request, pk):
    """선택한 내역의 정산 처리를 취소하고 미지급 상태로 되돌림"""
    supplier = get_object_or_404(BookSupplier, pk=pk)

    if request.method == 'POST':
        # 선택된 로그 ID들 가져오기
        selected_ids = request.POST.getlist('log_ids')

        if selected_ids:
            # 정산 취소 (is_paid=False, payment_date=None)
            updated_count = BookStockLog.objects.filter(
                id__in=selected_ids,
                supplier=supplier
            ).update(is_paid=False, payment_date=None)

            messages.warning(request, f"{updated_count}건의 정산이 취소되었습니다. '미지급 내역'으로 복구되었습니다.")
        else:
            messages.error(request, "취소할 내역을 선택해주세요.")

    return redirect('supplier_detail', pk=pk)


def supplier_settle(request, pk):
    """선택한 입고 내역 정산(입금) 처리"""
    supplier = get_object_or_404(BookSupplier, pk=pk)

    if request.method == 'POST':
        # 1. 선택된 로그 ID들 가져오기
        selected_ids = request.POST.getlist('log_ids')
        payment_date = request.POST.get('payment_date')

        if not selected_ids:
            messages.error(request, "정산할 내역을 선택해주세요.")
            return redirect('supplier_detail', pk=pk)

        # 2. 업데이트 (정산 완료 처리 + 날짜 기록)
        updated_count = BookStockLog.objects.filter(
            id__in=selected_ids,
            supplier=supplier
        ).update(is_paid=True, payment_date=payment_date)

        messages.success(request, f"{updated_count}건의 내역이 정산 처리되었습니다. (지급일: {payment_date})")

    return redirect('supplier_detail', pk=pk)


def search_book_api(request):
    """국립중앙도서관 API 조회 (Key 수정 및 데이터 정제)"""
    isbn = request.GET.get('isbn')

    # API
    API_KEY = "a36e5ab3c6a0d4359b7fffbca22dd34734921dea812fcdf66f711abf3ee10aae"

    if not isbn:
        return JsonResponse({'error': 'ISBN이 제공되지 않았습니다.'}, status=400)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    url = "https://www.nl.go.kr/NL/search/openApi/search.do"
    params = {
        'key': API_KEY,
        'kwd': isbn,
        'detailSearch': 'true',
        'f1': 'isbn',
        'category': '도서',
        'apiType': 'json'
    }

    try:
        # 타임아웃은 안전하게 5초
        response = requests.get(url, params=params, headers=headers, verify=False, timeout=5)

        if response.status_code != 200:
            return JsonResponse({'error': 'API 서버 접속 실패'}, status=500)

        data = response.json()

        # total이 문자열일 수도, 숫자일 수도 있어서 안전하게 변환
        total = int(data.get('total', 0))

        if total > 0:
            # result 키 사용
            items = data.get('result', [])

            if items:
                item = items[0]

                # [핵심 수정] 로그에 찍힌 정확한 Key 이름(camelCase) 사용
                title = item.get('titleInfo', '')
                author_raw = item.get('authorInfo', '')
                publisher = item.get('pubInfo', '')

                # 가격 정보는 로그에 없었으므로 일단 '0'으로 두거나 priceInfo 시도
                price_raw = item.get('priceInfo', '0')

                # [데이터 정제 1] 저자 정보에서 '지은이:' 제거
                # 예: "지은이: 유시민" -> "유시민"
                author = author_raw.replace('지은이:', '').strip()

                # [데이터 정제 2] 가격 정보에서 숫자만 추출
                price = str(price_raw).replace('원', '').replace(',', '').strip()
                if not price or not price.isdigit():
                    price = '0'

                result = {
                    'title': title,
                    'author': author,
                    'publisher': publisher,
                    'price': price,
                }
                print(f"🎉 최종 데이터 매핑 성공: {result}")
                return JsonResponse(result)
            else:
                return JsonResponse({'error': '도서 정보 리스트가 비어있습니다.'}, status=404)
        else:
            return JsonResponse({'error': '해당 도서 정보가 없습니다.'}, status=404)

    except Exception as e:
        print(f"🔥 에러 발생: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def book_sale_create(request, student_pk):
    """학생에게 교재 판매(분배) 및 재고/미납금 처리"""
    student = get_object_or_404(Student, pk=student_pk)

    if request.method == 'POST':
        form = BookSaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.student = student
            book = sale.book

            # 1. 재고 재확인
            if book.stock < sale.quantity:
                messages.error(request, f"재고가 부족합니다. (현재 재고: {book.stock}권)")
                return redirect('student_detail', pk=student.pk)

            try:
                with transaction.atomic():
                    # 2. 판매 날짜 설정
                    if sale.is_paid:
                        sale.payment_date = timezone.localtime(timezone.now()).date()
                    sale.save()

                    # 3. 재고 차감
                    book.stock -= sale.quantity
                    book.save()

                    # 4. 학생 미납금(unpaid_amount) 증가 (미납인 경우만)
                    if not sale.is_paid:
                        total_price = sale.price * sale.quantity
                        # 이제 모델에 필드가 있으므로 에러가 안 납니다!
                        student.unpaid_amount += total_price
                        student.save()

                    msg = f"'{book.title}' {sale.quantity}권이 지급되었습니다."
                    if not sale.is_paid:
                        msg += " (비용이 미납금에 합산되었습니다)"
                    messages.success(request, msg)

            except Exception as e:
                messages.error(request, f"처리 중 오류 발생: {e}")

            return redirect('student_detail', pk=student.pk)
    else:
        # 초기값에 오늘 날짜(한국 시간) 넣어주기
        form = BookSaleForm(initial={
            'sale_date': timezone.localtime(timezone.now()).date()
        })

    return render(request, 'bookstore/book_sale_form.html', {
        'form': form,
        'student': student
    })


def book_sale_settle(request, pk):
    """개별 교재 판매 건 납부(정산) 처리 (디버깅 추가)"""
    print(f"🕵️‍♂️ [디버깅] 납부 처리 요청 받음 - Sale ID: {pk}")
    sale = get_object_or_404(BookSale, pk=pk)

    if request.method == 'POST':
        print("📝 [디버깅] POST 요청 확인.")
        payment_date = request.POST.get('payment_date')
        print(f"📅 [디버깅] 제출된 납부일: {payment_date}")

        if not payment_date:
            print("❌ [디버깅] 납부일이 누락되었습니다.")
            messages.error(request, "납부일이 입력되지 않았습니다.")
            return redirect('student_detail', pk=sale.student.pk)

        try:
            with transaction.atomic():
                # 1. 판매 기록 업데이트 (결제 완료)
                sale.is_paid = True
                # 날짜 형식이 맞는지 확인 (YYYY-MM-DD)
                sale.payment_date = payment_date
                sale.save()
                print("💾 [디버깅] 판매 기록 업데이트 완료 (결제 상태 변경).")

                # 2. 학생 미납금 차감
                total_price = sale.get_total_price()
                sale.student.unpaid_amount -= total_price
                sale.student.save()
                print(f"💰 [디버깅] 학생 미납금 차감 완료. (남은 미납액: {sale.student.unpaid_amount})")

                messages.success(request, f"'{sale.book.title}' 납부 처리가 완료되었습니다.")

        except Exception as e:
            print(f"🔥 [디버깅] 처리 중 치명적 에러 발생: {e}")
            import traceback
            print(traceback.format_exc())  # 에러 상세 내용 출력
            messages.error(request, f"처리 중 오류 발생: {e}")

    else:
        print("⚠️ [디버깅] POST 요청이 아닙니다.")

    return redirect('student_detail', pk=sale.student.pk)

