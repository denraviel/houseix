from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from sales.models import Sale
from stays.models import GuestStay


class Invoice(models.Model):
    TYPE_GUEST_STAY = 'guest_stay'
    TYPE_SALE = 'sale'
    INVOICE_TYPE_CHOICES = [
        (TYPE_GUEST_STAY, 'Guest Stay'),
        (TYPE_SALE, 'Sales'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_UNPAID = 'unpaid'
    STATUS_PARTIALLY_PAID = 'partially_paid'
    STATUS_PAID = 'paid'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_PARTIALLY_PAID, 'Partially Paid'),
        (STATUS_PAID, 'Paid'),
    ]

    invoice_type = models.CharField(
        max_length=20,
        choices=INVOICE_TYPE_CHOICES,
        default=TYPE_GUEST_STAY,
        db_index=True,
    )
    stay = models.OneToOneField(
        GuestStay,
        on_delete=models.PROTECT,
        related_name='invoice',
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
    )
    invoice_number = models.CharField(max_length=20, unique=True, blank=True, editable=False, db_index=True)
    invoice_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_invoices',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def clean(self):
        if self.invoice_type == self.TYPE_GUEST_STAY:
            if not self.stay_id:
                raise ValidationError({'stay': 'Guest-stay invoices must be linked to a guest stay.'})
            if self.stay.status == GuestStay.STATUS_CANCELLED:
                raise ValidationError({'stay': 'Cancelled stays cannot have invoices.'})
            if not self.customer_id:
                self.customer = self.stay.customer
        elif self.invoice_type == self.TYPE_SALE:
            if self.stay_id:
                raise ValidationError({'stay': 'Standalone sales invoices cannot be linked to a guest stay.'})
        else:
            raise ValidationError({'invoice_type': 'Invalid invoice type.'})

        if self.assigned_to and self.assigned_to.role != 'staff':
            raise ValidationError({'assigned_to': 'Invoices can only be assigned to staff users.'})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        super().save(*args, **kwargs)
        if is_new and not self.invoice_number:
            invoice_number = f"INV{self.pk:06d}"
            type(self).objects.filter(pk=self.pk, invoice_number='').update(invoice_number=invoice_number)
            self.invoice_number = invoice_number

    def get_absolute_url(self):
        return reverse('invoice_detail', kwargs={'pk': self.pk})

    @property
    def is_sales_invoice(self):
        return self.invoice_type == self.TYPE_SALE

    @property
    def is_guest_stay_invoice(self):
        return self.invoice_type == self.TYPE_GUEST_STAY

    @property
    def display_customer(self):
        return self.customer or (self.stay.customer if self.stay_id else None)

    @property
    def room(self):
        return self.stay.room if self.stay_id else None

    @property
    def status_badge_class(self):
        mapping = {
            self.STATUS_DRAFT: 'secondary',
            self.STATUS_UNPAID: 'danger',
            self.STATUS_PARTIALLY_PAID: 'warning text-dark',
            self.STATUS_PAID: 'success',
        }
        return mapping.get(self.status, 'secondary')

    @property
    def billable_days(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).billable_days()

    @property
    def charge_end_date(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).charge_end_date()

    @property
    def is_provisional(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).is_provisional()

    @property
    def room_charge_total(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).room_charge_total()

    @property
    def product_charge_total(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).product_charge_total()

    @property
    def grand_total(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).grand_total()

    @property
    def room_payments_total(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).room_payments_total()

    @property
    def product_payments_total(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).product_payments_total()

    @property
    def total_payments(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).total_payments()

    @property
    def room_balance(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).room_balance()

    @property
    def product_balance(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).product_balance()

    @property
    def balance(self):
        from .services import InvoiceCalculationService
        return InvoiceCalculationService(self).balance()

    @property
    def is_fully_paid(self):
        return self.balance == Decimal('0.00') and self.grand_total > Decimal('0.00')

    def refresh_status(self, *, user=None, notes=''):
        from .services import InvoiceStatusService
        return InvoiceStatusService.refresh(self, user=user, notes=notes)


class InvoiceSale(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='sales')
    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name='invoice_link')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sale__created_at']
        constraints = [
            models.UniqueConstraint(fields=('invoice', 'sale'), name='unique_invoice_sale'),
        ]

    def clean(self):
        if self.invoice_id and self.invoice.invoice_type != Invoice.TYPE_SALE:
            raise ValidationError({'invoice': 'InvoiceSale can only be attached to standalone sales invoices.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InvoicePaymentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_void=False)


class InvoicePayment(models.Model):
    TYPE_ROOM = 'room'
    TYPE_PRODUCT = 'product'

    PAYMENT_TYPE_CHOICES = [
        (TYPE_ROOM, 'Room'),
        (TYPE_PRODUCT, 'Product'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=Sale.PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_payments_received',
    )
    received_by_full_name = models.CharField(max_length=255, blank=True)
    received_by_username = models.CharField(max_length=255, blank=True)
    received_by_role = models.CharField(max_length=50, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    is_void = models.BooleanField(default=False)
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_payments_voided',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InvoicePaymentQuerySet.as_manager()

    class Meta:
        ordering = ['-received_at', '-created_at']

    def __str__(self):
        return f"{self.get_payment_type_display()} payment of {self.amount} for {self.invoice}"

    def clean(self):
        if not self.invoice_id:
            raise ValidationError({'invoice': 'Payment must be linked to an invoice.'})
        if self.invoice.is_guest_stay_invoice and self.invoice.stay.status == GuestStay.STATUS_CANCELLED:
            raise ValidationError({'invoice': 'Payments cannot be recorded against a cancelled stay.'})
        if self.invoice.is_sales_invoice and self.payment_type != self.TYPE_PRODUCT:
            raise ValidationError({'payment_type': 'Standalone sales invoices only accept product payments.'})
        if self.amount is None or self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Payment amount must be greater than zero.'})
        if self.is_void and not self.void_reason:
            raise ValidationError({'void_reason': 'Please provide a reason for voiding this payment.'})

        other_payments = self.invoice.payments.active().exclude(pk=self.pk)
        paid_total = other_payments.filter(payment_type=self.payment_type).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        if self.payment_type == self.TYPE_ROOM:
            allowed_total = self.invoice.room_charge_total
        else:
            allowed_total = self.invoice.product_charge_total
        remaining_balance = allowed_total - paid_total
        if self.amount > remaining_balance:
            label = 'room' if self.payment_type == self.TYPE_ROOM else 'product'
            raise ValidationError({'amount': f'Payment exceeds the remaining {label} balance.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Invoice payments cannot be deleted. Void the payment instead.')

    def void(self, *, user=None, reason=''):
        if self.is_void:
            return self
        self.is_void = True
        self.void_reason = reason or 'Voided'
        self.voided_at = timezone.now()
        self.voided_by = user
        self.save(update_fields=['is_void', 'void_reason', 'voided_at', 'voided_by', 'updated_at'])
        InvoiceAuditLog.log(
            invoice=self.invoice,
            action_type=InvoiceAuditLog.ACTION_PAYMENT_VOIDED,
            user=user,
            payment=self,
            notes=self.void_reason,
        )
        self.invoice.refresh_status(user=user, notes='Payment voided.')
        return self


class InvoiceAuditLog(models.Model):
    ACTION_CREATED = 'invoice_created'
    ACTION_UPDATED = 'invoice_updated'
    ACTION_STATUS_CHANGED = 'invoice_status_changed'
    ACTION_PAYMENT_RECORDED = 'payment_recorded'
    ACTION_PAYMENT_VOIDED = 'payment_voided'
    ACTION_PRINTED = 'invoice_printed'
    ACTION_PDF_EXPORTED = 'invoice_pdf_exported'

    ACTION_CHOICES = [
        (ACTION_CREATED, 'Invoice Created'),
        (ACTION_UPDATED, 'Invoice Updated'),
        (ACTION_STATUS_CHANGED, 'Invoice Status Changed'),
        (ACTION_PAYMENT_RECORDED, 'Payment Recorded'),
        (ACTION_PAYMENT_VOIDED, 'Payment Voided'),
        (ACTION_PRINTED, 'Invoice Printed'),
        (ACTION_PDF_EXPORTED, 'Invoice PDF Exported'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='audit_logs')
    payment = models.ForeignKey(
        InvoicePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    user_full_name = models.CharField(max_length=255, blank=True)
    user_username = models.CharField(max_length=255, blank=True)
    user_role = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.invoice}"

    @classmethod
    def log(cls, *, invoice, action_type, user=None, payment=None, notes=''):
        return cls.objects.create(
            invoice=invoice,
            payment=payment,
            action_type=action_type,
            user=user,
            user_full_name=(getattr(user, 'full_name', '') or ''),
            user_username=(getattr(user, 'email', '') or ''),
            user_role=(getattr(user, 'role', '') or ''),
            notes=notes or '',
        )
