from django.urls import path
from . import views

urlpatterns = [
    path('', views.SaleListView.as_view(), name='sales_list'),
    path('create/', views.SaleCreateView.as_view(), name='sale_create'),
    path('<int:pk>/', views.SaleDetailView.as_view(), name='sale_detail'),
    path('<int:pk>/delete/', views.SaleDeleteView.as_view(), name='sale_delete'),
    path('<int:pk>/generate-invoice/', views.SaleInvoiceGenerateView.as_view(), name='sale_generate_invoice'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order_create'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    path('orders/<int:pk>/generate-invoice/', views.OrderInvoiceGenerateView.as_view(), name='order_generate_invoice'),
    path('<int:pk>/mark-prepared/', views.SaleMarkPreparedView.as_view(), name='sale_mark_prepared'),
    path('<int:pk>/cancel/', views.SaleCancelView.as_view(), name='sale_cancel'),
]
