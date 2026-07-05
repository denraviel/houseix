from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import CustomUser

from .models import Expense, ExpenseAuditLog, ExpenseCategory, RecurringExpense, Vendor
from .services import ExpenseApprovalService, ExpenseService, FuelLogService, RecurringExpenseService


class ExpenseServiceTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            email='owner@example.com',
            password='password123',
            full_name='Owner User',
            phone_number='1234567890',
            role='owner',
        )
        self.manager = CustomUser.objects.create_user(
            email='manager@example.com',
            password='password123',
            full_name='Manager User',
            phone_number='1234567891',
            role='manager',
        )
        self.category = ExpenseCategory.objects.get(code='DIESEL')
        self.vendor = Vendor.objects.create(
            name='Power Vendor',
            created_by=self.owner,
            updated_by=self.owner,
        )

    def test_create_expense_generates_number_and_audit_log(self):
        expense = ExpenseService.create_expense(
            cleaned_data={
                'category': self.category,
                'vendor': self.vendor,
                'task': None,
                'amount': Decimal('15000.00'),
                'payment_method': 'transfer',
                'expense_date': date.today(),
                'description': 'Generator diesel purchase',
                'receipt': None,
                'notes': 'Night shift purchase',
            },
            user=self.manager,
        )
        self.assertEqual(expense.expense_number, f'EXP{expense.pk:06d}')
        self.assertEqual(expense.status, Expense.STATUS_DRAFT)
        self.assertTrue(
            ExpenseAuditLog.objects.filter(expense=expense, action_type=ExpenseAuditLog.ACTION_CREATED).exists()
        )

    def test_submit_and_approve_expense_updates_workflow(self):
        expense = ExpenseService.create_expense(
            cleaned_data={
                'category': self.category,
                'vendor': self.vendor,
                'task': None,
                'amount': Decimal('25000.00'),
                'payment_method': 'cash',
                'expense_date': date.today(),
                'description': 'Generator overhaul',
                'receipt': None,
                'notes': '',
            },
            user=self.manager,
        )
        ExpenseService.submit_for_approval(expense=expense, user=self.manager)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.STATUS_PENDING_APPROVAL)
        ExpenseApprovalService.approve_expense(expense=expense, user=self.owner)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.STATUS_APPROVED)
        self.assertEqual(expense.approved_by, self.owner)
        self.assertIsNotNone(expense.approved_at)

    def test_recurring_generation_creates_expenses_and_moves_next_due_date(self):
        recurring = RecurringExpense.objects.create(
            category=self.category,
            vendor=self.vendor,
            description='Monthly generator service contract',
            amount=Decimal('5000.00'),
            frequency=RecurringExpense.FREQUENCY_MONTHLY,
            next_due_date=date(2026, 1, 15),
            created_by=self.owner,
            updated_by=self.owner,
        )
        generated = RecurringExpenseService.generate_due_expenses(user=self.owner, as_of=date(2026, 2, 16))
        recurring.refresh_from_db()
        self.assertEqual(len(generated), 2)
        self.assertEqual(recurring.last_generated, date(2026, 2, 15))
        self.assertEqual(recurring.next_due_date, date(2026, 3, 15))

    def test_fuel_log_statistics_are_computed(self):
        expense = ExpenseService.create_expense(
            cleaned_data={
                'category': self.category,
                'vendor': self.vendor,
                'task': None,
                'amount': Decimal('30000.00'),
                'payment_method': 'transfer',
                'expense_date': date.today(),
                'description': 'Bulk diesel purchase',
                'receipt': None,
                'notes': '',
            },
            user=self.manager,
        )
        fuel_log = FuelLogService.create_fuel_log(
            cleaned_data={
                'expense': expense,
                'generator_name': 'Main Generator',
                'opening_litres': Decimal('50.00'),
                'purchased_litres': Decimal('100.00'),
                'closing_litres': Decimal('20.00'),
                'generator_hours': Decimal('10.00'),
                'notes': '',
            },
            user=self.manager,
        )
        stats = FuelLogService.statistics(type(fuel_log).objects.all())
        self.assertEqual(stats['total_cost'], Decimal('30000.00'))
        self.assertEqual(stats['total_purchased_litres'], Decimal('100.00'))
        self.assertEqual(stats['total_litres_used'], Decimal('130.00'))
        self.assertEqual(stats['cost_per_hour'], Decimal('3000.00'))
