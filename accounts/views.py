from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.utils import OperationalError
from .forms import CustomLoginForm, StaffForm, StaffUpdateForm
from .models import CustomUser
from .permissions import OperationalModuleAccessMixin
from .services import NavigationService


def home(request):
    if request.user.is_authenticated:
        if request.user.role in ['owner', 'admin', 'manager']:
            return redirect('admin_dashboard')
        else:
            return redirect('employee_dashboard')
    return redirect('login')


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    return redirect('login')


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager']:
            return redirect('employee_dashboard')
        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != 'owner':
            messages.error(request, 'Only the owner can perform this action!')
            return redirect('admin_dashboard')
        return super().dispatch(request, *args, **kwargs)


class OwnerAdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin']:
            return redirect('employee_dashboard')
        return super().dispatch(request, *args, **kwargs)


class StaffListView(OperationalModuleAccessMixin, AdminRequiredMixin, ListView):
    module_code = NavigationService.MODULE_STAFF_MANAGEMENT
    model = CustomUser
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff_list'
    ordering = ['-date_joined']

    def get_queryset(self):
        if self.request.user.role == 'manager':
            return CustomUser.objects.filter(role='staff').prefetch_related('positions').order_by('-date_joined')
        return CustomUser.objects.all().prefetch_related('positions').order_by('-date_joined')


class StaffCreateView(OperationalModuleAccessMixin, AdminRequiredMixin, CreateView):
    module_code = NavigationService.MODULE_STAFF_MANAGEMENT
    model = CustomUser
    form_class = StaffForm
    template_name = 'accounts/staff_form.html'
    success_url = reverse_lazy('staff_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.role == 'owner':
            kwargs['allowed_roles'] = ['owner', 'admin', 'manager', 'staff']
        elif self.request.user.role == 'admin':
            kwargs['allowed_roles'] = ['manager', 'staff']
        elif self.request.user.role == 'manager':
            kwargs['allowed_roles'] = ['staff']
        return kwargs

    def form_valid(self, form):
        allowed_roles = ['staff']
        if self.request.user.role == 'owner':
            allowed_roles = ['owner', 'admin', 'manager', 'staff']
        elif self.request.user.role == 'admin':
            allowed_roles = ['manager', 'staff']
        elif self.request.user.role == 'manager':
            allowed_roles = ['staff']
        if form.cleaned_data.get('role') not in allowed_roles:
            messages.error(self.request, 'You are not authorized to create this type of user.')
            return redirect('staff_list')
        response = super().form_valid(form)
        messages.success(self.request, 'Staff account created successfully!')
        from .models import AuditLog
        AuditLog.log(self.request.user, 'user_created', f"Created user {self.object.email} ({self.object.role})")
        return response


class StaffUpdateView(OperationalModuleAccessMixin, AdminRequiredMixin, UpdateView):
    module_code = NavigationService.MODULE_STAFF_MANAGEMENT
    model = CustomUser
    form_class = StaffUpdateForm
    template_name = 'accounts/staff_form.html'
    success_url = reverse_lazy('staff_list')
    context_object_name = 'staff'

    def form_valid(self, form):
        if self.object.role in ['owner', 'admin'] and self.request.user.role != 'owner':
            messages.error(self.request, 'Only the owner can modify owner/admin accounts.')
            return redirect('staff_list')
        allowed_roles = ['staff']
        if self.request.user.role == 'owner':
            allowed_roles = ['owner', 'admin', 'manager', 'staff']
        elif self.request.user.role == 'admin':
            allowed_roles = ['manager', 'staff']
        elif self.request.user.role == 'manager':
            allowed_roles = ['staff']
        if form.cleaned_data.get('role') not in allowed_roles:
            messages.error(self.request, 'You are not authorized to set this role.')
            return redirect('staff_list')
        response = super().form_valid(form)
        messages.success(self.request, 'Staff details updated successfully!')
        from .models import AuditLog
        AuditLog.log(self.request.user, 'user_edited', f"Edited user {self.object.email} ({self.object.role})")
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.role == 'owner':
            kwargs['allowed_roles'] = ['owner', 'admin', 'manager', 'staff']
        elif self.request.user.role == 'admin':
            kwargs['allowed_roles'] = ['manager', 'staff']
        elif self.request.user.role == 'manager':
            kwargs['allowed_roles'] = ['staff']
        return kwargs

class StaffDeleteView(OperationalModuleAccessMixin, AdminRequiredMixin, DeleteView):
    module_code = NavigationService.MODULE_STAFF_MANAGEMENT
    model = CustomUser
    template_name = 'accounts/staff_confirm_delete.html'
    success_url = reverse_lazy('staff_list')
    context_object_name = 'staff'

    def delete(self, request, *args, **kwargs):
        staff = self.get_object()
        if request.user.role not in ['owner', 'admin']:
            messages.error(request, 'Only owner/admin can delete user accounts.')
            return redirect('staff_list')
        if staff.role == 'owner':
            messages.error(request, 'Owner accounts cannot be deleted.')
            return redirect('staff_list')
        if staff.role == 'admin' and request.user.role != 'owner':
            messages.error(request, 'Only the owner can delete admin accounts.')
            return redirect('staff_list')
        messages.success(request, 'Staff account deleted successfully!')
        from .models import AuditLog
        AuditLog.log(request.user, 'user_edited', f"Deleted user {staff.email} ({staff.role})")
        return super().delete(request, *args, **kwargs)


@login_required
def toggle_staff_active(request, pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return redirect('employee_dashboard')
    
    staff = get_object_or_404(CustomUser, pk=pk)
    if staff.role in ['owner', 'admin'] and request.user.role != 'owner':
        messages.error(request, 'Only the owner can activate/deactivate owner/admin accounts.')
        return redirect('staff_list')
    staff.is_active = not staff.is_active
    staff.save()
    if staff.is_active:
        messages.success(request, 'Staff account activated successfully!')
    else:
        messages.success(request, 'Staff account deactivated successfully!')
    
    from .models import AuditLog
    AuditLog.log(request.user, 'user_status_changed', f"Toggled active for {staff.email} to {staff.is_active}")
    return redirect('staff_list')


@login_required
def admin_dashboard(request):
    if request.user.role not in ['owner', 'admin', 'manager']:
        return redirect('employee_dashboard')
    from sales.models import Sale
    from inventory.models import InventoryItem
    from products.models import Product
    try:
        from tasks.models import Task, PerformanceRating
    except Exception:
        Task = None
        PerformanceRating = None
    from django.db.models import Sum
    from datetime import datetime, date

    total_sales = Sale.objects.count()
    total_inventory = InventoryItem.objects.count()
    
    total_staff = CustomUser.objects.count()
    active_staff = CustomUser.objects.filter(is_active=True).count()
    recent_staff = CustomUser.objects.order_by('-date_joined')[:5]
    
    # Get top selling products
    top_selling_products = Product.objects.annotate(
        total_sold=Sum('sales__quantity')
    ).order_by('-total_sold')[:5]
    
    # Get low stock products
    low_stock_products = Product.objects.filter(quantity_in_stock__lte=5)
    
    # Get recent sales
    recent_sales = Sale.objects.order_by('-created_at')[:5]
    
    # Get today's total revenue
    today = date.today()
    today_sales = Sale.objects.filter(created_at__date=today)
    today_revenue = today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0

    tasks_today_assigned = 0
    tasks_today_pending = 0
    tasks_today_in_progress = 0
    tasks_today_completed = 0
    tasks_overdue = 0
    top_performers = []

    if Task is not None:
        try:
            tasks_today = Task.objects.filter(date_assigned=today)
            tasks_today_assigned = tasks_today.count()
            tasks_today_pending = tasks_today.filter(status='pending').count()
            tasks_today_in_progress = tasks_today.filter(status='in_progress').count()
            tasks_today_completed = tasks_today.filter(status='completed').count()
            tasks_overdue = Task.objects.filter(status__in=['pending', 'in_progress'], due_date__lt=today).count()
        except OperationalError:
            pass

    if PerformanceRating is not None:
        try:
            top_performers = (
                PerformanceRating.objects.filter(date_rated__year=today.year, date_rated__month=today.month)
                .values('staff', 'staff__full_name')
                .annotate(avg_rating=models.Avg('rating'))
                .order_by('-avg_rating')[:3]
            )
        except OperationalError:
            top_performers = []

    context = {
        'dashboard_title': NavigationService.get_dashboard_title(request.user),
        'dashboard_widgets': NavigationService.get_dashboard_widgets(request.user),
        'total_sales': total_sales,
        'total_inventory': total_inventory,
        'total_staff': total_staff,
        'active_staff': active_staff,
        'recent_staff': recent_staff,
        'top_selling_products': top_selling_products,
        'low_stock_products': low_stock_products,
        'recent_sales': recent_sales,
        'today_revenue': today_revenue,
        'tasks_today_assigned': tasks_today_assigned,
        'tasks_today_completed': tasks_today_completed,
        'tasks_today_in_progress': tasks_today_in_progress,
        'tasks_today_pending': tasks_today_pending,
        'tasks_overdue': tasks_overdue,
        'top_performers': top_performers,
    }
    return render(request, 'accounts/admin_dashboard.html', context)


@login_required
def employee_dashboard(request):
    if request.user.role in ['owner', 'admin']:
        return redirect('admin_dashboard')
    from tasks.models import Task, PerformanceRating

    task_queryset = Task.objects.prefetch_related('required_positions').filter(assigned_to=request.user)
    pending_tasks = task_queryset.filter(status='pending')
    in_progress_tasks = task_queryset.filter(status='in_progress')
    completed_tasks = task_queryset.filter(status='completed')
    ratings = PerformanceRating.objects.filter(staff=request.user)[:5]
    avg_rating = PerformanceRating.objects.filter(staff=request.user).aggregate(models.Avg('rating'))['rating__avg'] or 0
    if avg_rating >= 4.5:
        category = 'Excellent Performer'
    elif avg_rating >= 3.5:
        category = 'Good Performer'
    elif avg_rating >= 2.5:
        category = 'Needs Improvement'
    else:
        category = 'Performance Concern'

    context = {
        'dashboard_title': NavigationService.get_dashboard_title(request.user),
        'dashboard_widgets': NavigationService.get_dashboard_widgets(request.user),
        'pending_tasks': pending_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'ratings': ratings,
        'avg_rating': avg_rating,
        'category': category,
    }
    return render(request, 'accounts/employee_dashboard.html', context)
