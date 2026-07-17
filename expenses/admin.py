from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Expense, ExpenseAuditLog, ExpenseCategory, FuelLog, RecurringExpense, Vendor


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'phone', 'email')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_number', 'category', 'amount', 'status', 'expense_date', 'recorded_by', 'approved_by')
    list_filter = ('status', 'payment_method', 'category')
    search_fields = ('expense_number', 'description', 'vendor__name', 'task__title')


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'frequency', 'next_due_date', 'last_generated', 'is_active')
    list_filter = ('frequency', 'is_active')
    search_fields = ('category__name', 'description', 'vendor__name')


@admin.register(FuelLog)
class FuelLogAdmin(admin.ModelAdmin):
    list_display = ('generator_name', 'expense', 'purchased_litres', 'generator_hours', 'recorded_by', 'created_at')
    search_fields = ('generator_name', 'expense__expense_number')


@admin.register(ExpenseAuditLog)
class ExpenseAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'expense', 'user_full_name', 'created_at')
    list_filter = ('action_type', 'user_role')
    search_fields = ('expense__expense_number', 'notes', 'user_full_name')