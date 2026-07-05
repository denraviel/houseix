from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from sales.models import Sale
from products.models import Product
from inventory.models import InventoryItem
from accounts.models import CustomUser, ActivityLog
from expenses.selectors import expense_report_snapshot


@login_required
def reports_dashboard(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')
    
    context = {
        'active_tab': 'dashboard',
    }
    try:
        context['expense_snapshot'] = expense_report_snapshot()
    except Exception:
        context['expense_snapshot'] = {
            'this_month_approved_total': 0,
            'this_month_approved_count': 0,
            'pending_approval_count': 0,
            'top_categories': [],
        }
    return render(request, 'reports/dashboard.html', context)


@login_required
def sales_report(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    sales_query = Sale.objects.all()
    
    if start_date:
        sales_query = sales_query.filter(created_at__date__gte=start_date)
    if end_date:
        sales_query = sales_query.filter(created_at__date__lte=end_date)
    
    # Overall stats
    total_revenue = sales_query.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_sales_count = sales_query.count()
    avg_sale_value = sales_query.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
    
    # Daily sales
    daily_sales = sales_query.extra(
        {'date': 'date(created_at)'}
    ).values('date').annotate(
        daily_revenue=Sum('total_amount'),
        daily_count=Count('id')
    ).order_by('-date')[:30]
    
    # Sales by category
    sales_by_category = sales_query.values(
        'product__category'
    ).annotate(
        category_revenue=Sum('total_amount'),
        category_count=Count('id')
    ).order_by('-category_revenue')
    
    # Sales by payment method
    sales_by_payment = sales_query.values(
        'payment_method'
    ).annotate(
        payment_revenue=Sum('total_amount'),
        payment_count=Count('id')
    ).order_by('-payment_revenue')
    
    # Today's stats
    today_sales = Sale.objects.filter(created_at__date=today)
    today_revenue = today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    today_count = today_sales.count()
    
    # This week's stats
    week_sales = Sale.objects.filter(created_at__date__gte=week_ago)
    week_revenue = week_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    week_count = week_sales.count()
    
    # This month's stats
    month_sales = Sale.objects.filter(created_at__date__gte=month_ago)
    month_revenue = month_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    month_count = month_sales.count()
    
    context = {
        'active_tab': 'sales',
        'total_revenue': total_revenue,
        'total_sales_count': total_sales_count,
        'avg_sale_value': avg_sale_value,
        'daily_sales': daily_sales,
        'sales_by_category': sales_by_category,
        'sales_by_payment': sales_by_payment,
        'today_revenue': today_revenue,
        'today_count': today_count,
        'week_revenue': week_revenue,
        'week_count': week_count,
        'month_revenue': month_revenue,
        'month_count': month_count,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/sales_report.html', context)


@login_required
def inventory_report(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')
    
    # Low stock items (products)
    low_stock_products = Product.objects.filter(
        quantity_in_stock__lte=5
    ).order_by('quantity_in_stock')
    
    # Low stock items (inventory)
    low_stock_inventory = InventoryItem.objects.filter(
        quantity__lte=F('low_stock_threshold')
    ).order_by('quantity')
    
    # Stock value by category
    product_stock_by_category = Product.objects.values(
        'category'
    ).annotate(
        total_quantity=Sum('quantity_in_stock'),
        total_cost_value=Sum(F('quantity_in_stock') * F('cost_price')),
        total_sell_value=Sum(F('quantity_in_stock') * F('selling_price'))
    ).order_by('-total_sell_value')
    
    inventory_stock_by_category = InventoryItem.objects.values(
        'category'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_value=Sum(F('quantity') * F('cost_price'))
    ).order_by('-total_value')
    
    # Total stock value
    total_product_cost_value = Product.objects.aggregate(
        total=Sum(F('quantity_in_stock') * F('cost_price'))
    )['total'] or 0
    
    total_product_sell_value = Product.objects.aggregate(
        total=Sum(F('quantity_in_stock') * F('selling_price'))
    )['total'] or 0
    
    total_inventory_value = InventoryItem.objects.aggregate(
        total=Sum(F('quantity') * F('cost_price'))
    )['total'] or 0
    
    total_products = Product.objects.count()
    total_inventory_items = InventoryItem.objects.count()
    
    context = {
        'active_tab': 'inventory',
        'low_stock_products': low_stock_products,
        'low_stock_inventory': low_stock_inventory,
        'product_stock_by_category': product_stock_by_category,
        'inventory_stock_by_category': inventory_stock_by_category,
        'total_product_cost_value': total_product_cost_value,
        'total_product_sell_value': total_product_sell_value,
        'total_inventory_value': total_inventory_value,
        'total_products': total_products,
        'total_inventory_items': total_inventory_items,
    }
    return render(request, 'reports/inventory_report.html', context)


@login_required
def product_performance_report(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')
    
    # Top selling products
    top_products = Product.objects.annotate(
        total_sold=Sum('sales__quantity'),
        total_revenue=Sum('sales__total_amount')
    ).filter(total_sold__gt=0).order_by('-total_sold')
    
    # Products with no sales
    no_sales_products = Product.objects.filter(
        sales__isnull=True
    )
    
    # Profit margin per product
    products_with_profit = []
    for product in top_products:
        if product.total_sold:
            cost_per_unit = product.cost_price
            sell_per_unit = product.selling_price
            profit_per_unit = sell_per_unit - cost_per_unit
            total_profit = profit_per_unit * product.total_sold
            profit_margin = (profit_per_unit / sell_per_unit * 100) if sell_per_unit > 0 else 0
            products_with_profit.append({
                'product': product,
                'total_sold': product.total_sold,
                'total_revenue': product.total_revenue or 0,
                'profit_per_unit': profit_per_unit,
                'total_profit': total_profit,
                'profit_margin': profit_margin,
            })
    
    context = {
        'active_tab': 'products',
        'products_with_profit': products_with_profit,
        'no_sales_products': no_sales_products,
    }
    return render(request, 'reports/product_performance.html', context)


@login_required
def staff_performance_report(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')
    
    # Staff sales performance
    staff_sales = CustomUser.objects.annotate(
        total_sales=Count('sale'),
        total_revenue=Sum('sale__total_amount')
    ).filter(total_sales__gt=0).order_by('-total_revenue')
    
    context = {
        'active_tab': 'staff',
        'staff_sales': staff_sales,
    }
    return render(request, 'reports/staff_performance.html', context)


@login_required
def activity_report(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        from django.shortcuts import redirect
        return redirect('employee_dashboard')

    now = timezone.now()
    range_key = (request.GET.get('range') or 'today').strip()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if range_key == 'today':
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
    elif range_key == 'week':
        start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = start_of_week
        end_dt = start_dt + timedelta(days=7)
    elif range_key == 'month':
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_dt.month == 12:
            end_dt = start_dt.replace(year=start_dt.year + 1, month=1)
        else:
            end_dt = start_dt.replace(month=start_dt.month + 1)
    else:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else now.date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else now.date()
        except ValueError:
            start = now.date()
            end = now.date()
        start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), datetime.min.time()))
        range_key = 'custom'

    logs = ActivityLog.objects.filter(timestamp__gte=start_dt, timestamp__lt=end_dt)

    customers_created = logs.filter(action_type='customer_created').values(
        'user_full_name', 'user_role'
    ).annotate(total=Count('id')).order_by('-total', 'user_full_name')

    checkins = logs.filter(action_type='guest_checked_in').values(
        'user_full_name', 'user_role'
    ).annotate(total=Count('id')).order_by('-total', 'user_full_name')

    checkouts = logs.filter(action_type='guest_checked_out').values(
        'user_full_name', 'user_role'
    ).annotate(total=Count('id')).order_by('-total', 'user_full_name')

    recent_logs = logs.select_related('customer', 'booking').order_by('-timestamp')[:200]

    context = {
        'active_tab': 'activity',
        'range': range_key,
        'start_date': start_date,
        'end_date': end_date,
        'customers_created': customers_created,
        'checkins': checkins,
        'checkouts': checkouts,
        'recent_logs': recent_logs,
    }
    return render(request, 'reports/activity_report.html', context)
