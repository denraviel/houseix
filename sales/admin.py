from django.contrib import admin
from .models import Order, Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'quantity', 'status', 'total_amount', 'actual_cogs',
        'recorded_by', 'prepared_by', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'created_at', 'recorded_by')
    search_fields = ('product__name',)
    date_hierarchy = 'created_at'


class SaleInline(admin.TabularInline):
    model = Sale
    extra = 0
    fields = ('product', 'quantity', 'total_amount', 'status')
    readonly_fields = ('total_amount',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'room', 'payment_method', 'recorded_by', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('customer__full_name',)
    date_hierarchy = 'created_at'
    inlines = [SaleInline]
