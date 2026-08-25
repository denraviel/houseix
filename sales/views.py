from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, CreateView, DeleteView

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
        queryset = SalesAccessService.sales_queryset_for_user(self.request.user)
        return queryset.select_related('invoice_link__invoice')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_manage'] = self.request.user.role in ['owner', 'admin', 'manager']
        return context


class SaleDetailView(OperationalModuleAccessMixin, LoginRequiredMixin, DetailView):
    module_code = NavigationService.MODULE_SALES
    model = Sale
    template_name = 'sales/sale_detail.html'
    context_object_name = 'sale'

    def get_queryset(self):
        return SalesAccessService.sales_queryset_for_user(self.request.user).select_related(
            'invoice_link__invoice',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = self.object
        has_invoice = hasattr(sale, 'invoice_link') and sale.invoice_link_id
        context['has_invoice'] = has_invoice
        context['linked_invoice'] = sale.invoice_link.invoice if has_invoice else None
        context['can_generate_invoice'] = self.request.user.role in ['owner', 'admin', 'manager']
        context['can_manage'] = self.request.user.role in ['owner', 'admin', 'manager']
        return context


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
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, 'Sale recorded successfully!')
        if self.request.user.role in ['owner', 'admin', 'manager']:
            return reverse('sale_detail', kwargs={'pk': self.object.pk})
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


class SaleInvoiceGenerateView(OperationalModuleAccessMixin, LoginRequiredMixin, View):
    module_code = NavigationService.MODULE_SALES

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager']:
            return HttpResponseForbidden("You don't have permission to generate sales invoices.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        sale = get_object_or_404(
            SalesAccessService.sales_queryset_for_user(request.user),
            pk=pk,
        )
        from invoices.services import InvoiceGeneratorService
        try:
            invoice = InvoiceGeneratorService.generate_for_sale(sale=sale, user=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('sale_detail', pk=sale.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect('sale_detail', pk=sale.pk)

        if hasattr(sale, 'invoice_link') and sale.invoice_link.invoice_id == invoice.id:
            messages.info(request, f'Sale already has invoice {invoice.invoice_number}.')
        else:
            messages.success(request, f'Sales invoice {invoice.invoice_number} generated successfully.')
        return redirect(invoice.get_absolute_url())
