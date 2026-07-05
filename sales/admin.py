from django.contrib import admin
from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'unit_price', 'total_amount', 'payment_method', 'recorded_by', 'created_at')
    list_filter = ('payment_method', 'created_at', 'recorded_by')
    search_fields = ('product__name',)
    date_hierarchy = 'created_at'
