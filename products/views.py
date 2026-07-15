from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Product
from .forms import ProductForm
from accounts.views import AdminRequiredMixin, OwnerAdminRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from accounts.permissions import OperationalModuleAccessMixin, module_permission_required
from accounts.services import NavigationService


class ProductListView(OperationalModuleAccessMixin, AdminRequiredMixin, ListView):
    module_code = NavigationService.MODULE_PRODUCTS
    model = Product
    template_name = 'products/product_list_v2.html'
    context_object_name = 'products'
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(category__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['low_stock_products'] = Product.objects.filter(quantity_in_stock__lte=5)
        return context


class ProductCreateView(OperationalModuleAccessMixin, AdminRequiredMixin, CreateView):
    module_code = NavigationService.MODULE_PRODUCTS
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('product_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Product created successfully!')
        response = super().form_valid(form)
        from accounts.models import AuditLog
        AuditLog.log(self.request.user, 'product_created', f"Created product {self.object.name}")
        return response


class ProductUpdateView(OperationalModuleAccessMixin, AdminRequiredMixin, UpdateView):
    module_code = NavigationService.MODULE_PRODUCTS
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('product_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Product updated successfully!')
        response = super().form_valid(form)
        from accounts.models import AuditLog
        AuditLog.log(self.request.user, 'product_updated', f"Updated product {self.object.name}")
        return response


@login_required
@module_permission_required(NavigationService.MODULE_PRODUCTS)
def product_toggle_active(request, pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        messages.error(request, 'You are not authorized to perform this action.')
        return redirect('employee_dashboard')
    product = get_object_or_404(Product, pk=pk)
    product.is_available = not product.is_available
    product.save(update_fields=['is_available'])
    from accounts.models import AuditLog
    AuditLog.log(request.user, 'product_toggled', f"Toggled product {product.name} active to {product.is_available}")
    return redirect('product_list')


class ProductDeleteView(OperationalModuleAccessMixin, OwnerAdminRequiredMixin, DeleteView):
    module_code = NavigationService.MODULE_PRODUCTS
    model = Product
    template_name = 'products/product_confirm_delete.html'
    success_url = reverse_lazy('product_list')
    
    def delete(self, request, *args, **kwargs):
        product = self.get_object()
        messages.success(self.request, 'Product deleted successfully!')
        from accounts.models import AuditLog
        AuditLog.log(request.user, 'product_deleted', f"Deleted product {product.name}")
        return super().delete(request, *args, **kwargs)
