from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Expense, FuelLog, RecurringExpense
from .services import FuelLogService


def accessible_expenses_queryset(user):
    queryset = Expense.objects.select_related(
        'category', 'vendor', 'task', 'approved_by', 'recorded_by', 'created_by', 'updated_by'
    )
    if getattr(user, 'role', None) == 'staff':
        queryset = queryset.filter(Q(recorded_by=user) | Q(created_by=user))
    return queryset


def approved_expenses_queryset(*, start_date=None, end_date=None):
    queryset = Expense.objects.filter(status=Expense.STATUS_APPROVED).select_related('category', 'vendor', 'task')
    if start_date:
        queryset = queryset.filter(expense_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(expense_date__lte=end_date)
    return queryset


def recurring_due_queryset(*, as_of=None):
    as_of = as_of or timezone.localdate()
    return RecurringExpense.objects.filter(is_active=True, next_due_date__lte=as_of).select_related(
        'category', 'vendor'
    )


def expense_summary_by_category(*, start_date=None, end_date=None):
    return (
        approved_expenses_queryset(start_date=start_date, end_date=end_date)
        .values('category__name', 'category__code')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'category__name')
    )


def expense_summary_by_vendor(*, start_date=None, end_date=None):
    return (
        approved_expenses_queryset(start_date=start_date, end_date=end_date)
        .values('vendor__name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'vendor__name')
    )


def daily_expense_rows(*, start_date=None, end_date=None):
    return (
        approved_expenses_queryset(start_date=start_date, end_date=end_date)
        .annotate(day=TruncDate('expense_date'))
        .values('day')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-day')
    )


def fuel_logs_queryset(*, start_date=None, end_date=None):
    queryset = FuelLog.objects.select_related('expense', 'expense__category', 'expense__vendor', 'recorded_by')
    if start_date:
        queryset = queryset.filter(expense__expense_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(expense__expense_date__lte=end_date)
    return queryset


def fuel_report_statistics(*, start_date=None, end_date=None):
    return FuelLogService.statistics(fuel_logs_queryset(start_date=start_date, end_date=end_date))


def expense_dashboard_snapshot(user, *, as_of=None):
    as_of = as_of or timezone.localdate()
    month_start = as_of.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    accessible_qs = accessible_expenses_queryset(user)
    approved_qs = accessible_qs.filter(status=Expense.STATUS_APPROVED)
    pending_qs = accessible_qs.filter(status=Expense.STATUS_PENDING_APPROVAL)
    approved_today_qs = approved_qs.filter(approved_at__date=as_of)
    month_approved_qs = approved_qs.filter(expense_date__gte=month_start, expense_date__lte=month_end)
    today_approved_qs = approved_qs.filter(expense_date=as_of)
    month_fuel_logs = fuel_logs_queryset(start_date=month_start, end_date=month_end).filter(
        expense__status=Expense.STATUS_APPROVED
    )

    return {
        'today_total': today_approved_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'month_total': month_approved_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'pending_approval_count': pending_qs.count(),
        'approved_today_count': approved_today_qs.count(),
        'recurring_due_count': recurring_due_queryset(as_of=as_of).count(),
        'fuel_purchased_this_month': sum((log.purchased_litres for log in month_fuel_logs), Decimal('0.00')),
        'recent_expenses': accessible_qs.order_by('-created_at')[:8],
        'recent_fuel_logs': fuel_logs_queryset().order_by('-created_at')[:8],
        'category_breakdown': list(expense_summary_by_category(start_date=month_start, end_date=month_end)[:8]),
        'month_start': month_start,
        'month_end': month_end,
    }


def expense_report_snapshot(*, as_of=None):
    as_of = as_of or timezone.localdate()
    month_start = as_of.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    month_approved = approved_expenses_queryset(start_date=month_start, end_date=month_end)
    pending_qs = Expense.objects.filter(status=Expense.STATUS_PENDING_APPROVAL)
    return {
        'this_month_approved_total': month_approved.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'this_month_approved_count': month_approved.count(),
        'pending_approval_count': pending_qs.count(),
        'top_categories': list(expense_summary_by_category(start_date=month_start, end_date=month_end)[:5]),
    }
