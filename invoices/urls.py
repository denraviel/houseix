from django.urls import path

from . import views


urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='invoice_list'),
    path('create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('history/', views.InvoiceHistoryView.as_view(), name='invoice_history'),
    path('generate/<int:stay_id>/', views.InvoiceGenerateView.as_view(), name='invoice_generate'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_update'),
    path('<int:pk>/payment/', views.InvoicePaymentView.as_view(), name='invoice_payment'),
    path('<int:pk>/print/', views.InvoicePrintView.as_view(), name='invoice_print'),
    path('<int:pk>/pdf/', views.InvoicePDFView.as_view(), name='invoice_pdf'),
]
