from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
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
        from inventory.services import InsufficientStockError
        try:
            return super().form_valid(form)
        except InsufficientStockError as exc:
            form.add_error(
                None,
                f"Cannot complete this sale: not enough {exc.item.item_name} in stock "
                f"(needed {exc.requested} {exc.item.unit_type}, have {exc.available})."
            )
            return self.form_invalid(form)

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


class SaleMarkPreparedView(OperationalModuleAccessMixin, LoginRequiredMixin, View):
    """
    The single point where a kitchen order actually transitions to
    prepared/served - this is what triggers recipe ingredient consumption,
    NOT order creation. See SaleWorkflowService.mark_prepared.
    """
    module_code = NavigationService.MODULE_SALES

    def post(self, request, pk):
        sale = get_object_or_404(
            SalesAccessService.sales_queryset_for_user(request.user),
            pk=pk,
        )
        from inventory.services import InsufficientStockError
        from .services import SaleWorkflowService
        try:
            SaleWorkflowService.mark_prepared(sale=sale, user=request.user)
            messages.success(request, f'Order #{sale.pk} marked as prepared/served. Inventory consumption recorded.')
        except InsufficientStockError as exc:
            messages.error(
                request,
                f"Cannot prepare this order: not enough {exc.item.item_name} in stock "
                f"(needed {exc.requested} {exc.item.unit_type}, have {exc.available})."
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('sale_detail', pk=sale.pk)


class SaleCancelView(OperationalModuleAccessMixin, LoginRequiredMixin, View):
    """Cancels an order BEFORE it consumes any ingredients (pre-consumption statuses only)."""
    module_code = NavigationService.MODULE_SALES

    def post(self, request, pk):
        sale = get_object_or_404(
            SalesAccessService.sales_queryset_for_user(request.user),
            pk=pk,
        )
        from .services import SaleWorkflowService
        reason = request.POST.get('reason', '')
        try:
            SaleWorkflowService.cancel(sale=sale, user=request.user, reason=reason)
            messages.success(request, f'Order #{sale.pk} cancelled. No inventory was consumed.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('sale_detail', pk=sale.pk)


class OrderCreateView(OperationalModuleAccessMixin, LoginRequiredMixin, View):
    """
    Multi-item order entry: shared ticket details once, then any number of
    product lines. Lines whose ingredients are short are reported back and
    left out; everything else still goes through, so one unavailable dish
    doesn't kill the whole order.
    """
    module_code = NavigationService.MODULE_SALES

    def get(self, request):
        from .forms import OrderForm, OrderItemFormSet
        return render(request, 'sales/order_form.html', {
            'order_form': OrderForm(user=request.user),
            'item_formset': OrderItemFormSet(queryset=Sale.objects.none(), form_kwargs={'user': request.user}),
        })

    def post(self, request):
        from django.db import transaction as db_transaction
        from .forms import OrderForm, OrderItemFormSet
        from .models import Order

        order_form = OrderForm(request.POST, user=request.user)
        item_formset = OrderItemFormSet(
            request.POST, queryset=Sale.objects.none(), form_kwargs={'user': request.user},
        )

        order_form_valid = order_form.is_valid()
        item_formset.is_valid()  # populate per-form errors without short-circuiting

        valid_lines = []
        flagged = []
        for form in item_formset.forms:
            product = form.cleaned_data.get('product') if form.cleaned_data else None
            quantity = form.cleaned_data.get('quantity') if form.cleaned_data else None
            if form.errors:
                if product:
                    flagged.append((product, form.errors.get('__all__', form.errors)))
                continue
            if product and quantity:
                valid_lines.append((product, quantity))

        if not order_form_valid:
            return render(request, 'sales/order_form.html', {
                'order_form': order_form, 'item_formset': item_formset,
            })

        if not valid_lines:
            messages.error(request, 'No items could be added to this order. Check the errors on each line.')
            return render(request, 'sales/order_form.html', {
                'order_form': order_form, 'item_formset': item_formset,
            })

        from inventory.services import InsufficientStockError
        try:
            with db_transaction.atomic():
                order = order_form.save(commit=False)
                order.recorded_by = request.user
                if order.stay_id:
                    order.customer = order.stay.customer
                    order.room = order.stay.room
                order.save()
                for product, quantity in valid_lines:
                    Sale.objects.create(
                        order=order, product=product, quantity=quantity,
                        payment_method=order.payment_method, recorded_by=request.user,
                    )
        except InsufficientStockError as exc:
            messages.error(
                request,
                f"Order could not be saved: not enough {exc.item.item_name} "
                f"(needed {exc.requested} {exc.item.unit_type}, have {exc.available})."
            )
            return render(request, 'sales/order_form.html', {
                'order_form': order_form, 'item_formset': item_formset,
            })

        if flagged:
            for product, errors in flagged:
                messages.warning(request, f"{product.name} was left off this order - {'; '.join(errors)}")
            messages.success(request, f'Order #{order.pk} created with {len(valid_lines)} item(s). Some items were skipped.')
        else:
            messages.success(request, f'Order #{order.pk} created with {len(valid_lines)} item(s).')
        return redirect('order_detail', pk=order.pk)


class OrderDetailView(OperationalModuleAccessMixin, LoginRequiredMixin, DetailView):
    module_code = NavigationService.MODULE_SALES
    template_name = 'sales/order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        from .models import Order
        return Order.objects.select_related('customer', 'room', 'stay', 'recorded_by').prefetch_related('items__product')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_manage'] = self.request.user.role in ['owner', 'admin', 'manager']
        return context


class OrderInvoiceGenerateView(OperationalModuleAccessMixin, LoginRequiredMixin, View):
    """One invoice covering every (non-cancelled) line on the order."""
    module_code = NavigationService.MODULE_SALES

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager']:
            return HttpResponseForbidden("You don't have permission to generate sales invoices.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        from .models import Order
        from invoices.services import InvoiceGeneratorService
        order = get_object_or_404(Order, pk=pk)
        try:
            invoice = InvoiceGeneratorService.generate_for_order(order=order, user=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('order_detail', pk=order.pk)
        messages.success(request, f'Invoice {invoice.invoice_number} generated for order #{order.pk}.')
        return redirect(invoice.get_absolute_url())
