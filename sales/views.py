from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, DeleteView
from django.urls import reverse_lazy

from accounts.permissions import OperationalModuleAccessMixin
from accounts.views import OwnerRequiredMixin
from accounts.services import NavigationService

from .forms import SaleForm
from .models import Sale
from .services import SalesAccessService


class SaleListView(OperationalModuleAccessMixin, ListView):
    module_code = NavigationService.MODULE_SALES
    model = Sale
    template_name = 'sales/sales_list.html'
    context_object_name = 'sales'
    ordering = ['-created_at']

    def get_queryset(self):
        return SalesAccessService.sales_queryset_for_user(self.request.user)


class SaleCreateView(OperationalModuleAccessMixin, LoginRequiredMixin, CreateView):
    module_code = NavigationService.MODULE_SALES
    model = Sale
    form_class = SaleForm
    template_name = 'sales/sale_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, 'Sale recorded successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        if self.request.user.role in ['owner', 'admin', 'manager']:
            return reverse_lazy('sales_list')
        return reverse_lazy('employee_dashboard')


class SaleDeleteView(OperationalModuleAccessMixin, OwnerRequiredMixin, DeleteView):
    module_code = NavigationService.MODULE_SALES
    model = Sale
    template_name = 'sales/sale_confirm_delete.html'
    success_url = reverse_lazy('sales_list')
    context_object_name = 'sale'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Sale record deleted successfully!')
        return super().delete(request, *args, **kwargs)
