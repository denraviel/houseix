from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from accounts.permissions import OperationalModuleAccessMixin
from accounts.services import NavigationService
from stays.models import GuestStay

from .forms import InvoiceCreateForm, InvoiceFilterForm, InvoicePaymentForm, InvoiceUpdateForm
from .models import Invoice, InvoiceAuditLog
from .permissions import InvoiceAccessMixin, InvoiceManagerRequiredMixin, can_record_payments
from .services import InvoiceCalculationService, InvoiceGeneratorService, InvoicePDFService, InvoicePaymentService


class InvoiceListView(OperationalModuleAccessMixin, ListView):
    module_code = NavigationService.MODULE_INVOICES
    model = Invoice
    template_name = 'invoices/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager', 'staff']:
            return HttpResponseForbidden("You don't have permission to access this page.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Invoice.objects.select_related(
            'stay__customer', 'stay__room', 'created_by', 'updated_by', 'assigned_to'
        )
        if self.request.user.role == 'staff':
            queryset = queryset.filter(assigned_to=self.request.user)
        self.filter_form = InvoiceFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            query = (self.filter_form.cleaned_data.get('q') or '').strip()
            status = self.filter_form.cleaned_data.get('status')
            if query:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=query)
                    | Q(stay__customer__full_name__icontains=query)
                    | Q(stay__customer__customer_id__icontains=query)
                    | Q(stay__room__room_number__icontains=query)
                )
            if status:
                queryset = queryset.filter(status=status)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        context['can_manage'] = self.request.user.role in ['owner', 'admin', 'manager']
        return context


class InvoiceDetailView(InvoiceAccessMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return Invoice.objects.select_related(
            'stay__customer', 'stay__room', 'created_by', 'updated_by', 'assigned_to'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calculations = InvoiceCalculationService(self.object)
        context.update(calculations.build_context())
        context['charge_mode_text'] = (
            "Provisional balance based on today's date because the stay is still active."
            if context.get('is_provisional')
            else 'Final balance based on recorded checkout date.'
        )
        context['room_label'] = f'Room {context["room"].room_number} ({context["room"].get_room_type_display()})'
        context['ownership_details'] = {
            'created_by': self.object.created_by.full_name if self.object.created_by else '-',
            'updated_by': self.object.updated_by.full_name if self.object.updated_by else '-',
            'assigned_to': self.object.assigned_to.full_name if self.object.assigned_to else '-',
            'notes': self.object.notes or 'No notes added.',
        }
        context['recent_activity_rows'] = [
            {
                'action': entry.get_action_type_display(),
                'meta': f"{entry.user_full_name or 'System'} - {entry.created_at.strftime('%Y-%m-%d %H:%M')}",
                'notes': entry.notes or '-',
            }
            for entry in self.object.audit_logs.select_related('user', 'payment')[:10]
        ]
        context['can_manage'] = self.request.user.role in ['owner', 'admin', 'manager']
        context['can_record_payments'] = can_record_payments(self.request.user, self.object)
        return context


class InvoiceCreateView(InvoiceManagerRequiredMixin, FormView):
    template_name = 'invoices/invoice_create.html'
    form_class = InvoiceCreateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['invoice_date'] = self.request.GET.get('invoice_date') or None
        stay_id = self.request.GET.get('stay')
        if stay_id:
            initial['stay'] = stay_id
        return initial

    def form_valid(self, form):
        try:
            invoice = InvoiceGeneratorService.generate(
                stay=form.cleaned_data['stay'],
                user=self.request.user,
                invoice_date=form.cleaned_data['invoice_date'],
                notes=form.cleaned_data['notes'],
                assigned_to=form.cleaned_data['assigned_to'],
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f'Invoice {invoice.invoice_number} created successfully.')
        return redirect(invoice.get_absolute_url())


class InvoiceUpdateView(InvoiceManagerRequiredMixin, FormView):
    template_name = 'invoices/invoice_create.html'
    form_class = InvoiceUpdateForm

    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(
            Invoice.objects.select_related('stay__customer', 'stay__room', 'assigned_to'),
            pk=kwargs['pk'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            'invoice_date': self.invoice.invoice_date,
            'assigned_to': self.invoice.assigned_to,
            'notes': self.invoice.notes,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.invoice
        context['mode'] = 'edit'
        return context

    def form_valid(self, form):
        InvoiceGeneratorService.update_invoice(
            invoice=self.invoice,
            user=self.request.user,
            invoice_date=form.cleaned_data['invoice_date'],
            notes=form.cleaned_data['notes'],
            assigned_to=form.cleaned_data['assigned_to'],
        )
        messages.success(self.request, f'Invoice {self.invoice.invoice_number} updated successfully.')
        return redirect(self.invoice.get_absolute_url())


class InvoiceGenerateView(InvoiceManagerRequiredMixin, View):
    def post(self, request, stay_id):
        stay = get_object_or_404(GuestStay.objects.select_related('customer', 'room'), pk=stay_id)
        try:
            invoice = InvoiceGeneratorService.generate(stay=stay, user=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('stay_detail', pk=stay.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect('stay_detail', pk=stay.pk)
        messages.success(request, f'Invoice {invoice.invoice_number} generated successfully.')
        return redirect(invoice.get_absolute_url())


class InvoicePaymentView(InvoiceAccessMixin, FormView):
    template_name = 'invoices/invoice_payment.html'
    form_class = InvoicePaymentForm

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not can_record_payments(request.user, self.object):
            return HttpResponseForbidden("You don't have permission to record payments for this invoice.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Invoice.objects.select_related('stay__customer', 'stay__room', 'assigned_to')

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['invoice'] = self.object
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(InvoiceCalculationService(self.object).build_context())
        return context

    def form_valid(self, form):
        try:
            payment = InvoicePaymentService.record_payment(
                invoice=self.object,
                cleaned_data=form.cleaned_data,
                user=self.request.user,
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f'{payment.get_payment_type_display()} payment recorded for {self.object.invoice_number}.',
        )
        return redirect(self.object.get_absolute_url())


class InvoicePrintView(InvoiceAccessMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_print.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return Invoice.objects.select_related('stay__customer', 'stay__room', 'assigned_to')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        InvoiceAuditLog.log(
            invoice=self.object,
            action_type=InvoiceAuditLog.ACTION_PRINTED,
            user=request.user,
            notes='Opened print view.',
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(InvoiceCalculationService(self.object).build_context())
        return context


class InvoicePDFView(InvoiceAccessMixin, DetailView):
    model = Invoice

    def get_queryset(self):
        return Invoice.objects.select_related('stay__customer', 'stay__room', 'assigned_to')

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        InvoiceAuditLog.log(
            invoice=self.object,
            action_type=InvoiceAuditLog.ACTION_PDF_EXPORTED,
            user=request.user,
            notes='Generated invoice PDF.',
        )
        return InvoicePDFService.render(self.object)


class InvoiceHistoryView(OperationalModuleAccessMixin, ListView):
    module_code = NavigationService.MODULE_INVOICES
    model = InvoiceAuditLog
    template_name = 'invoices/invoice_history.html'
    context_object_name = 'history_entries'
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['owner', 'admin', 'manager', 'staff']:
            return HttpResponseForbidden("You don't have permission to access this page.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = InvoiceAuditLog.objects.select_related('invoice', 'payment', 'user', 'invoice__assigned_to')
        if self.request.user.role == 'staff':
            queryset = queryset.filter(invoice__assigned_to=self.request.user)
        query = (self.request.GET.get('q') or '').strip()
        if query:
            queryset = queryset.filter(
                Q(invoice__invoice_number__icontains=query)
                | Q(user_full_name__icontains=query)
                | Q(notes__icontains=query)
            )
        return queryset.order_by('-created_at')


@login_required
def invoice_redirect_home(request):
    return redirect('invoice_list')
