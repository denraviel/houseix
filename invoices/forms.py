from datetime import date

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from stays.models import GuestStay

from .models import Invoice, InvoicePayment


class BootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class InvoiceCreateForm(BootstrapFormMixin, forms.Form):
    stay = forms.ModelChoiceField(queryset=GuestStay.objects.none())
    invoice_date = forms.DateField(initial=date.today, widget=forms.DateInput(attrs={'type': 'date'}))
    assigned_to = forms.ModelChoiceField(queryset=None, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['stay'].queryset = (
            GuestStay.objects.select_related('customer', 'room')
            .exclude(status=GuestStay.STATUS_CANCELLED)
            .filter(invoice__isnull=True)
            .order_by('-created_at')
        )
        self.fields['stay'].label_from_instance = (
            lambda stay: f"Stay #{stay.pk} - {stay.customer.full_name} / Room {stay.room.room_number}"
        )
        from accounts.models import CustomUser

        self.fields['assigned_to'].queryset = CustomUser.objects.filter(role='staff', is_active=True).order_by(
            'full_name'
        )
        self.fields['assigned_to'].empty_label = 'Unassigned'
        self.fields['assigned_to'].help_text = 'Optional staff assignment for invoice follow-up and payment handling.'
        self._apply_bootstrap()

    def clean_stay(self):
        stay = self.cleaned_data['stay']
        if stay.status == GuestStay.STATUS_CANCELLED:
            raise forms.ValidationError('Cancelled stays cannot have invoices.')
        if hasattr(stay, 'invoice'):
            raise forms.ValidationError('This stay already has an invoice.')
        return stay


class InvoiceUpdateForm(BootstrapFormMixin, forms.Form):
    invoice_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    assigned_to = forms.ModelChoiceField(queryset=None, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import CustomUser

        self.fields['assigned_to'].queryset = CustomUser.objects.filter(role='staff', is_active=True).order_by(
            'full_name'
        )
        self.fields['assigned_to'].empty_label = 'Unassigned'
        self._apply_bootstrap()


class InvoicePaymentForm(BootstrapFormMixin, forms.Form):
    payment_type = forms.ChoiceField(choices=InvoicePayment.PAYMENT_TYPE_CHOICES)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    payment_method = forms.ChoiceField(choices=InvoicePayment._meta.get_field('payment_method').choices)
    reference = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice')
        super().__init__(*args, **kwargs)
        self.fields['payment_type'].help_text = (
            f"Room balance: N{self.invoice.room_balance:,.2f} | Product balance: N{self.invoice.product_balance:,.2f}"
        )
        self._apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data
        payment = InvoicePayment(
            invoice=self.invoice,
            payment_type=cleaned_data.get('payment_type'),
            amount=cleaned_data.get('amount') or 0,
            payment_method=cleaned_data.get('payment_method') or '',
            reference=cleaned_data.get('reference') or '',
            notes=cleaned_data.get('notes') or '',
        )
        try:
            payment.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, 'message_dict'):
                for field_name, messages in exc.message_dict.items():
                    if field_name in self.fields:
                        for message in messages:
                            self.add_error(field_name, message)
                    else:
                        for message in messages:
                            self.add_error(None, message)
            else:
                for message in exc.messages:
                    self.add_error(None, message)
        return cleaned_data


class InvoiceFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(Invoice.STATUS_CHOICES),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
