from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import ActivityLog
from accounts.permissions import module_permission_required
from accounts.services import NavigationService
from .forms import CustomerForm
from .models import Customer


def _can_create_customers(user):
    return user.role in ['owner', 'admin', 'manager', 'staff']


def _can_edit_customers(user):
    return user.role in ['owner', 'admin', 'manager']


def _can_delete_customers(user):
    return user.role in ['owner', 'admin']


@login_required
@module_permission_required(NavigationService.MODULE_CUSTOMERS)
def customer_list(request):
    query = (request.GET.get('q') or '').strip()
    customers = Customer.objects.all()
    if query:
        customers = customers.filter(
            Q(customer_id__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, 'customers/customer_list.html', {'customers': customers, 'query': query})


@login_required
@module_permission_required(NavigationService.MODULE_CUSTOMERS)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    stays = customer.stays.select_related('room').all().order_by('-created_at')
    return render(request, 'customers/customer_detail.html', {'customer': customer, 'stays': stays})


@login_required
@module_permission_required(NavigationService.MODULE_CUSTOMERS)
def customer_create(request):
    if not _can_create_customers(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    if request.method == 'POST':
        form = CustomerForm(request.POST, user=request.user)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by_user = request.user
            customer.created_by_full_name = request.user.full_name
            customer.created_by_username = request.user.email
            customer.created_by_role = request.user.role
            if request.user.role == 'staff':
                customer.is_active = True
            customer.save()
            ActivityLog.log(request.user, 'customer_created', customer=customer, notes=f"Created customer {customer.full_name}.")
            messages.success(request, f"Customer {customer.full_name} created.")
            return redirect('customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(user=request.user)
    return render(request, 'customers/customer_form.html', {'form': form, 'mode': 'create'})


@login_required
@module_permission_required(NavigationService.MODULE_CUSTOMERS)
def customer_update(request, pk):
    if not _can_edit_customers(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer, user=request.user)
        if form.is_valid():
            updated = form.save()
            ActivityLog.log(request.user, 'customer_updated', customer=updated, notes=f"Updated customer {updated.full_name}.")
            messages.success(request, f"Customer {updated.full_name} updated.")
            return redirect('customer_detail', pk=updated.pk)
    else:
        form = CustomerForm(instance=customer, user=request.user)
    return render(request, 'customers/customer_form.html', {'form': form, 'customer': customer, 'mode': 'edit'})


@login_required
@module_permission_required(NavigationService.MODULE_CUSTOMERS)
def customer_delete(request, pk):
    if not _can_delete_customers(request.user):
        return HttpResponseForbidden("You don't have permission to access this page.")
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        try:
            customer_name = customer.full_name
            customer.delete()
            messages.success(request, f"Customer {customer_name} deleted.")
            return redirect('customer_list')
        except ProtectedError:
            messages.error(request, 'This customer cannot be deleted because it has guest stay records.')
            return redirect('customer_detail', pk=customer.pk)
    return render(request, 'customers/customer_confirm_delete.html', {'customer': customer})
