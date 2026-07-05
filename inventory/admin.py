from django.contrib import admin
from .models import InventoryItem, StockMovement


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'quantity', 'unit_type', 'cost_price', 'low_stock_threshold', 'last_updated')
    list_filter = ('category', 'unit_type',)
    search_fields = ('item_name',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity_taken', 'taken_by', 'taken_at')
    list_filter = ('taken_at', 'taken_by')
    date_hierarchy = 'taken_at'
