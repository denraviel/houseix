from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from sales.models import Sale
from tasks.models import Task

from .validators import validate_category_code, validate_positive_value, validate_receipt_file


class TrackedModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ExpenseCategory(TrackedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True, validators=[validate_category_code])
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Expense categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)


class Vendor(TrackedModel):
    name = models.CharField(max_length=150, unique=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Expense(TrackedModel):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING_APPROVAL, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    expense_number = models.CharField(max_length=20, unique=True, blank=True, editable=False, db_index=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[validate_positive_value])
    payment_method = models.CharField(max_length=20, choices=Sale.PAYMENT_METHOD_CHOICES)
    expense_date = models.DateField(default=timezone.localdate)
    description = models.TextField()
    receipt = models.FileField(
        upload_to='expenses/receipts/%Y/%m/',
        null=True,
        blank=True,
        validators=[validate_receipt_file],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_expenses',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return self.expense_number or f'Expense #{self.pk}'

    def clean(self):
        if self.amount is None or self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Expense amount must be greater than zero.'})
        if self.status == self.STATUS_APPROVED:
            if not self.approved_by_id or not self.approved_at:
                raise ValidationError('Approved expenses must record the approver and approval time.')
        elif self.approved_by_id or self.approved_at:
            raise ValidationError('Only approved expenses can store approval details.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('expense_detail', kwargs={'pk': self.pk})

    @property
    def status_badge_class(self):
        return {
            self.STATUS_DRAFT: 'secondary',
            self.STATUS_PENDING_APPROVAL: 'warning text-dark',
            self.STATUS_APPROVED: 'success',
            self.STATUS_REJECTED: 'danger',
        }.get(self.status, 'secondary')

    @property
    def receipt_file_name(self):
        if not self.receipt:
            return ''
        return Path(self.receipt.name).name


class RecurringExpense(TrackedModel):
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_QUARTERLY = 'quarterly'
    FREQUENCY_YEARLY = 'yearly'

    FREQUENCY_CHOICES = [
        (FREQUENCY_WEEKLY, 'Weekly'),
        (FREQUENCY_MONTHLY, 'Monthly'),
        (FREQUENCY_QUARTERLY, 'Quarterly'),
        (FREQUENCY_YEARLY, 'Yearly'),
    ]

    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='recurring_expenses')
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_expenses',
    )
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[validate_positive_value])
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    next_due_date = models.DateField()
    last_generated = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['next_due_date', 'category__name']

    def __str__(self):
        return f'{self.category.name} - {self.get_frequency_display()}'

    @property
    def is_due(self):
        return self.is_active and self.next_due_date <= timezone.localdate()


class FuelLog(models.Model):
    expense = models.OneToOneField(Expense, on_delete=models.CASCADE, related_name='fuel_log')
    generator_name = models.CharField(max_length=150)
    opening_litres = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_litres = models.DecimalField(max_digits=10, decimal_places=2)
    closing_litres = models.DecimalField(max_digits=10, decimal_places=2)
    generator_hours = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_logs_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.generator_name} - {self.expense}'

    def clean(self):
        if not self.expense_id:
            raise ValidationError({'expense': 'Fuel logs must be linked to an expense.'})
        category_code = (self.expense.category.code or '').upper()
        category_name = (self.expense.category.name or '').strip().lower()
        if category_code != 'DIESEL' and category_name != 'diesel':
            raise ValidationError({'expense': 'Fuel logs can only be linked to Diesel expenses.'})
        if self.opening_litres < 0 or self.purchased_litres <= 0 or self.closing_litres < 0:
            raise ValidationError('Fuel litres must be valid positive values.')
        if self.generator_hours <= 0:
            raise ValidationError({'generator_hours': 'Generator hours must be greater than zero.'})
        if self.closing_litres > (self.opening_litres + self.purchased_litres):
            raise ValidationError({'closing_litres': 'Closing litres cannot exceed opening plus purchased litres.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def litres_used(self):
        return max((self.opening_litres + self.purchased_litres) - self.closing_litres, Decimal('0.00'))

    @property
    def cost_per_hour(self):
        if not self.generator_hours:
            return Decimal('0.00')
        return self.expense.amount / self.generator_hours

    @property
    def cost_per_litre(self):
        if not self.purchased_litres:
            return Decimal('0.00')
        return self.expense.amount / self.purchased_litres


class ExpenseAuditLog(models.Model):
    ACTION_CREATED = 'expense_created'
    ACTION_UPDATED = 'expense_updated'
    ACTION_SUBMITTED = 'expense_submitted'
    ACTION_APPROVED = 'expense_approved'
    ACTION_REJECTED = 'expense_rejected'
    ACTION_DELETED = 'expense_deleted'
    ACTION_RECEIPT_UPLOADED = 'receipt_uploaded'
    ACTION_FUEL_LOG_CREATED = 'fuel_log_created'
    ACTION_RECURRING_GENERATED = 'recurring_generated'

    ACTION_CHOICES = [
        (ACTION_CREATED, 'Expense Created'),
        (ACTION_UPDATED, 'Expense Updated'),
        (ACTION_SUBMITTED, 'Submitted for Approval'),
        (ACTION_APPROVED, 'Expense Approved'),
        (ACTION_REJECTED, 'Expense Rejected'),
        (ACTION_DELETED, 'Expense Deleted'),
        (ACTION_RECEIPT_UPLOADED, 'Receipt Uploaded'),
        (ACTION_FUEL_LOG_CREATED, 'Fuel Log Created'),
        (ACTION_RECURRING_GENERATED, 'Recurring Expense Generated'),
    ]

    expense = models.ForeignKey(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    fuel_log = models.ForeignKey(
        FuelLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    recurring_expense = models.ForeignKey(
        RecurringExpense,
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
        identifier = self.expense.expense_number if self.expense else 'Deleted expense'
        return f'{self.get_action_type_display()} - {identifier}'

    @classmethod
    def log(cls, *, action_type, user=None, expense=None, fuel_log=None, recurring_expense=None, notes=''):
        return cls.objects.create(
            action_type=action_type,
            user=user,
            expense=expense,
            fuel_log=fuel_log,
            recurring_expense=recurring_expense,
            user_full_name=(getattr(user, 'full_name', '') or ''),
            user_username=(getattr(user, 'email', '') or ''),
            user_role=(getattr(user, 'role', '') or ''),
            notes=notes or '',
        )
