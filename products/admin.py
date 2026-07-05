from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'selling_price', 'quantity_in_stock', 'is_available', 'status')
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'category')
