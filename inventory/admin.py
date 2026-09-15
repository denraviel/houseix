from django.contrib import admin
from .models import InventoryItem, StockMovement, StockBatch, InventoryTransaction


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'quantity', 'unit_type', 'cost_price', 'low_stock_threshold', 'last_updated')
    list_filter = ('category', 'unit_type',)
    search_fields = ('item_name',)


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity_received', 'quantity_remaining', 'unit_cost', 'purchased_at', 'is_opening_balance')
    list_filter = ('is_opening_balance', 'item__category')
    search_fields = ('item__item_name', 'supplier')
    date_hierarchy = 'purchased_at'
    readonly_fields = ('created_at',)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'item', 'transaction_type', 'quantity', 'previous_quantity', 'new_quantity',
        'unit_cost', 'total_cost', 'recipe', 'sale', 'performed_by', 'created_at',
    )
    list_filter = ('transaction_type', 'item__category', 'performed_by')
    search_fields = ('item__item_name', 'reference', 'reason', 'performed_by__full_name')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in InventoryTransaction._meta.fields]

    def has_delete_permission(self, request, obj=None):
        # Historical transactions should not be freely deleted.
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity_taken', 'taken_by', 'taken_at')
    list_filter = ('taken_at', 'taken_by')
    date_hierarchy = 'taken_at'
