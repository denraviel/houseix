from django.contrib import admin

from .models import Invoice, InvoiceAuditLog, InvoicePayment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'stay', 'invoice_date', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'invoice_date', 'created_at')
    search_fields = ('invoice_number', 'stay__customer__full_name', 'stay__room__room_number')


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'payment_type', 'amount', 'payment_method', 'received_by', 'received_at', 'is_void')
    list_filter = ('payment_type', 'payment_method', 'is_void', 'received_at')
    search_fields = ('invoice__invoice_number', 'reference', 'received_by_full_name')


@admin.register(InvoiceAuditLog)
class InvoiceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'action_type', 'user_full_name', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('invoice__invoice_number', 'user_full_name', 'notes')
