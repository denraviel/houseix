import calendar
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from sales.models import Sale

from .models import Expense, ExpenseAuditLog, FuelLog, RecurringExpense


def format_currency(value):
    amount = value or Decimal('0.00')
    return f'N{amount:,.2f}'


class ExpenseService:
    @staticmethod
    def validate_expense(expense):
        expense.full_clean()
        return expense

    @staticmethod
    def generate_expense_number(expense):
        if expense.expense_number:
            return expense.expense_number
        expense_number = f'EXP{expense.pk:06d}'
        Expense.objects.filter(pk=expense.pk, expense_number='').update(expense_number=expense_number)
        expense.expense_number = expense_number
        return expense_number

    @classmethod
    @transaction.atomic
    def create_expense(cls, *, cleaned_data, user):
        expense = Expense(
            expense_number='',
            category=cleaned_data['category'],
            vendor=cleaned_data.get('vendor'),
            task=cleaned_data.get('task'),
            amount=cleaned_data['amount'],
            payment_method=cleaned_data['payment_method'],
            expense_date=cleaned_data['expense_date'],
            description=cleaned_data['description'],
            receipt=cleaned_data.get('receipt'),
            notes=cleaned_data.get('notes', '') or '',
            status=Expense.STATUS_DRAFT,
            recorded_by=user,
            created_by=user,
            updated_by=user,
        )
        cls.validate_expense(expense)
        expense.save()
        cls.generate_expense_number(expense)
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_CREATED,
            user=user,
            expense=expense,
            notes=f'Created expense {expense.expense_number}.',
        )
        if expense.receipt:
            ExpenseAuditLog.log(
                action_type=ExpenseAuditLog.ACTION_RECEIPT_UPLOADED,
                user=user,
                expense=expense,
                notes=f'Uploaded receipt {expense.receipt_file_name}.',
            )
        return expense

    @staticmethod
    def _ensure_editable(expense, user):
        if expense.status == Expense.STATUS_APPROVED:
            raise ValidationError('Approved expenses cannot be edited.')
        if expense.status == Expense.STATUS_PENDING_APPROVAL and getattr(user, 'role', None) not in ['owner', 'admin']:
            raise ValidationError('Pending approval expenses can only be edited by owner or admin users.')

    @classmethod
    @transaction.atomic
    def update_expense(cls, *, expense, cleaned_data, user):
        cls._ensure_editable(expense, user)
        previous_receipt = expense.receipt.name if expense.receipt else ''
        expense.category = cleaned_data['category']
        expense.vendor = cleaned_data.get('vendor')
        expense.task = cleaned_data.get('task')
        expense.amount = cleaned_data['amount']
        expense.payment_method = cleaned_data['payment_method']
        expense.expense_date = cleaned_data['expense_date']
        expense.description = cleaned_data['description']
        new_receipt = cleaned_data.get('receipt')
        if new_receipt is False:
            expense.receipt = None
        elif new_receipt:
            expense.receipt = new_receipt
        expense.notes = cleaned_data.get('notes', '') or ''
        expense.updated_by = user
        cls.validate_expense(expense)
        expense.save()
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_UPDATED,
            user=user,
            expense=expense,
            notes=f'Updated expense {expense.expense_number}.',
        )
        current_receipt = expense.receipt.name if expense.receipt else ''
        if current_receipt and current_receipt != previous_receipt:
            ExpenseAuditLog.log(
                action_type=ExpenseAuditLog.ACTION_RECEIPT_UPLOADED,
                user=user,
                expense=expense,
                notes=f'Uploaded receipt {expense.receipt_file_name}.',
            )
        return expense

    @staticmethod
    @transaction.atomic
    def submit_for_approval(*, expense, user, notes=''):
        if expense.status not in [Expense.STATUS_DRAFT, Expense.STATUS_REJECTED]:
            raise ValidationError('Only draft or rejected expenses can be submitted for approval.')
        expense.status = Expense.STATUS_PENDING_APPROVAL
        expense.updated_by = user
        expense.save(update_fields=['status', 'updated_by', 'updated_at'])
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_SUBMITTED,
            user=user,
            expense=expense,
            notes=notes or f'Submitted {expense.expense_number} for approval.',
        )
        return expense

    @staticmethod
    @transaction.atomic
    def delete_expense(*, expense, user, notes=''):
        if expense.status == Expense.STATUS_APPROVED:
            raise ValidationError('Approved expenses cannot be deleted.')
        if expense.status == Expense.STATUS_PENDING_APPROVAL and getattr(user, 'role', None) not in ['owner', 'admin']:
            raise ValidationError('Only owner or admin users can delete pending approval expenses.')
        expense_number = expense.expense_number or f'Expense #{expense.pk}'
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_DELETED,
            user=user,
            expense=expense,
            notes=notes or f'Deleted {expense_number}.',
        )
        expense.delete()
        return expense_number


class ExpenseApprovalService:
    @staticmethod
    @transaction.atomic
    def approve_expense(*, expense, user, notes=''):
        if expense.status != Expense.STATUS_PENDING_APPROVAL:
            raise ValidationError('Only pending approval expenses can be approved.')
        expense.status = Expense.STATUS_APPROVED
        expense.approved_by = user
        expense.approved_at = timezone.now()
        expense.updated_by = user
        expense.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_by', 'updated_at'])
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_APPROVED,
            user=user,
            expense=expense,
            notes=notes or f'Approved {expense.expense_number}.',
        )
        return expense

    @staticmethod
    @transaction.atomic
    def reject_expense(*, expense, user, notes=''):
        if expense.status != Expense.STATUS_PENDING_APPROVAL:
            raise ValidationError('Only pending approval expenses can be rejected.')
        expense.status = Expense.STATUS_REJECTED
        expense.approved_by = None
        expense.approved_at = None
        expense.updated_by = user
        expense.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_by', 'updated_at'])
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_REJECTED,
            user=user,
            expense=expense,
            notes=notes or f'Rejected {expense.expense_number}.',
        )
        return expense


class RecurringExpenseService:
    DEFAULT_RECURRING_PAYMENT_METHOD = Sale.PAYMENT_METHOD_CHOICES[-1][0]

    @staticmethod
    def advance_due_date(date_value, frequency):
        if frequency == RecurringExpense.FREQUENCY_WEEKLY:
            return date_value + timedelta(days=7)
        month_step = {
            RecurringExpense.FREQUENCY_MONTHLY: 1,
            RecurringExpense.FREQUENCY_QUARTERLY: 3,
            RecurringExpense.FREQUENCY_YEARLY: 12,
        }.get(frequency)
        if month_step is None:
            raise ValidationError('Unsupported recurring frequency.')
        month_index = date_value.month - 1 + month_step
        year = date_value.year + (month_index // 12)
        month = (month_index % 12) + 1
        day = min(date_value.day, calendar.monthrange(year, month)[1])
        return date_value.replace(year=year, month=month, day=day)

    @classmethod
    @transaction.atomic
    def generate_due_expenses(cls, *, user, as_of=None, recurring_queryset=None):
        as_of = as_of or timezone.localdate()
        queryset = recurring_queryset or RecurringExpense.objects.filter(is_active=True, next_due_date__lte=as_of)
        generated = []
        for recurring in queryset.select_related('category', 'vendor'):
            next_due_date = recurring.next_due_date
            while recurring.is_active and next_due_date <= as_of:
                expense = ExpenseService.create_expense(
                    cleaned_data={
                        'category': recurring.category,
                        'vendor': recurring.vendor,
                        'task': None,
                        'amount': recurring.amount,
                        'payment_method': cls.DEFAULT_RECURRING_PAYMENT_METHOD,
                        'expense_date': next_due_date,
                        'description': recurring.description,
                        'receipt': None,
                        'notes': 'Generated from recurring schedule. Verify payment method before approval.',
                    },
                    user=user,
                )
                ExpenseAuditLog.log(
                    action_type=ExpenseAuditLog.ACTION_RECURRING_GENERATED,
                    user=user,
                    expense=expense,
                    recurring_expense=recurring,
                    notes=f'Generated from recurring schedule #{recurring.pk}.',
                )
                generated.append(expense)
                recurring.last_generated = next_due_date
                next_due_date = cls.advance_due_date(next_due_date, recurring.frequency)
            recurring.next_due_date = next_due_date
            recurring.updated_by = user
            recurring.save(update_fields=['last_generated', 'next_due_date', 'updated_by', 'updated_at'])
        return generated


class FuelLogService:
    @staticmethod
    def validate_metrics(*, opening_litres, purchased_litres, closing_litres, generator_hours):
        if opening_litres < 0 or purchased_litres <= 0 or closing_litres < 0:
            raise ValidationError('Fuel litre values must be valid positive numbers.')
        if generator_hours <= 0:
            raise ValidationError('Generator hours must be greater than zero.')
        if closing_litres > (opening_litres + purchased_litres):
            raise ValidationError('Closing litres cannot exceed opening plus purchased litres.')

    @classmethod
    @transaction.atomic
    def create_fuel_log(cls, *, cleaned_data, user):
        cls.validate_metrics(
            opening_litres=cleaned_data['opening_litres'],
            purchased_litres=cleaned_data['purchased_litres'],
            closing_litres=cleaned_data['closing_litres'],
            generator_hours=cleaned_data['generator_hours'],
        )
        fuel_log = FuelLog(
            expense=cleaned_data['expense'],
            generator_name=cleaned_data['generator_name'],
            opening_litres=cleaned_data['opening_litres'],
            purchased_litres=cleaned_data['purchased_litres'],
            closing_litres=cleaned_data['closing_litres'],
            generator_hours=cleaned_data['generator_hours'],
            notes=cleaned_data.get('notes', '') or '',
            recorded_by=user,
        )
        fuel_log.save()
        ExpenseAuditLog.log(
            action_type=ExpenseAuditLog.ACTION_FUEL_LOG_CREATED,
            user=user,
            expense=fuel_log.expense,
            fuel_log=fuel_log,
            notes=f'Created fuel log for {fuel_log.generator_name}.',
        )
        return fuel_log

    @staticmethod
    def statistics(queryset=None):
        queryset = queryset or FuelLog.objects.select_related('expense')
        total_cost = queryset.aggregate(total=Sum('expense__amount'))['total'] or Decimal('0.00')
        total_hours = sum((log.generator_hours for log in queryset), Decimal('0.00'))
        total_purchased_litres = sum((log.purchased_litres for log in queryset), Decimal('0.00'))
        total_litres_used = sum((log.litres_used for log in queryset), Decimal('0.00'))
        cost_per_hour = (total_cost / total_hours) if total_hours else Decimal('0.00')
        cost_per_litre = (total_cost / total_purchased_litres) if total_purchased_litres else Decimal('0.00')
        return {
            'total_cost': total_cost,
            'total_hours': total_hours,
            'total_purchased_litres': total_purchased_litres,
            'total_litres_used': total_litres_used,
            'cost_per_hour': cost_per_hour,
            'cost_per_litre': cost_per_litre,
        }
