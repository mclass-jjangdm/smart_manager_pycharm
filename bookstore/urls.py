# bookstore/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.book_list, name='book_list'),
    path('new/', views.book_create, name='book_create'),
    path('<int:pk>/edit/', views.book_update, name='book_update'),
    path('<int:pk>/delete/', views.book_delete, name='book_delete'),
    path('<int:pk>/restock/', views.book_restock, name='book_restock'),
    path('<int:pk>/', views.book_detail, name='book_detail'),
    path('<int:pk>/return/', views.book_return, name='book_return'),
    # 일괄 등록 URL
    path('upload/', views.book_upload, name='book_upload'),
    # 구매처 관리 url
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/new/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.supplier_update, name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    path('suppliers/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<int:pk>/settle/', views.supplier_settle, name='supplier_settle'),
    path('suppliers/<int:pk>/cancel/', views.supplier_payment_cancel, name='supplier_payment_cancel'),

    # API 검색용 URL
    path('api/search/', views.search_book_api, name='search_book_api'),

    path('sell/<int:student_pk>/', views.book_sale_create, name='book_sale_create'),

    # [추가] 개별 납부 처리 URL
    path('sale/<int:pk>/settle/', views.book_sale_settle, name='book_sale_settle'),
]