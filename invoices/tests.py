from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from customers.models import Customer
from products.models import Product
from rooms.models import Room
from sales.models import Sale
from stays.models import GuestStay

from .models import Invoice, InvoicePayment
from .services import InvoiceGeneratorService, InvoicePaymentService


class InvoiceModuleTests(TestCase):
    def setUp(self):
        self.manager = CustomUser.objects.create_user(
            email='manager@example.com',
            password='password123',
            full_name='Manager User',
            phone_number='08000000001',
            role='manager',
        )
        self.staff = CustomUser.objects.create_user(
            email='staff@example.com',
            password='password123',
            full_name='Staff User',
            phone_number='08000000002',
            role='staff',
        )
        self.customer = Customer.objects.create(
            full_name='Test Guest',
            phone_number='08000000003',
            created_by_user=self.manager,
            created_by_full_name=self.manager.full_name,
            created_by_username=self.manager.email,
            created_by_role=self.manager.role,
        )
        self.room = Room.objects.create(room_number='101', room_type=Room.TYPE_SINGLE, daily_rate=Decimal('15000.00'))
        self.product = Product.objects.create(
            name='Water',
            category='Drinks',
            selling_price=Decimal('1000.00'),
            cost_price=Decimal('500.00'),
            quantity_in_stock=10,
        )

    def _create_stay(self, *, status=GuestStay.STATUS_CHECKED_OUT, check_in_days_ago=3, check_out_days_ago=1):
        today = timezone.localdate()
        check_in_date = today - timedelta(days=check_in_days_ago)
        check_out_date = None
        if check_out_days_ago is not None:
            check_out_date = today - timedelta(days=check_out_days_ago)
        return GuestStay.objects.create(
            customer=self.customer,
            room=self.room,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            status=status,
            daily_rate=Decimal('15000.00'),
            created_by_user=self.manager,
            created_by_full_name=self.manager.full_name,
            created_by_username=self.manager.email,
            created_by_role=self.manager.role,
        )

    def test_generate_invoice_for_stay_creates_number_and_default_status(self):
        stay = self._create_stay()
        invoice = InvoiceGeneratorService.generate(stay=stay, user=self.manager, assigned_to=self.staff)

        self.assertTrue(invoice.invoice_number.startswith('INV'))
        self.assertEqual(invoice.status, Invoice.STATUS_UNPAID)
        self.assertEqual(invoice.assigned_to, self.staff)

    def test_duplicate_invoice_for_same_stay_is_blocked(self):
        stay = self._create_stay()
        InvoiceGeneratorService.generate(stay=stay, user=self.manager)

        with self.assertRaises(ValidationError):
            InvoiceGeneratorService.generate(stay=stay, user=self.manager)

    def test_invoice_reads_room_and_product_totals_from_existing_sources(self):
        stay = self._create_stay(
            status=GuestStay.STATUS_CHECKED_IN,
            check_in_days_ago=3,
            check_out_days_ago=None,
        )
        Sale.objects.create(
            stay=stay,
            product=self.product,
            quantity=2,
            payment_method='cash',
            recorded_by=self.manager,
            unit_price=Decimal('0.00'),
            total_amount=Decimal('0.00'),
        )
        stay.status = GuestStay.STATUS_CHECKED_OUT
        stay.check_out_date = timezone.localdate() - timedelta(days=1)
        stay.save(update_fields=['status', 'check_out_date', 'updated_at'])
        invoice = InvoiceGeneratorService.generate(stay=stay, user=self.manager)

        self.assertEqual(invoice.billable_days, 2)
        self.assertEqual(invoice.room_charge_total, Decimal('30000.00'))
        self.assertEqual(invoice.product_charge_total, Decimal('2000.00'))
        self.assertEqual(invoice.grand_total, Decimal('32000.00'))

    def test_active_stay_uses_today_as_provisional_charge_end_date(self):
        stay = self._create_stay(
            status=GuestStay.STATUS_CHECKED_IN,
            check_in_days_ago=2,
            check_out_days_ago=None,
        )
        invoice = InvoiceGeneratorService.generate(stay=stay, user=self.manager)

        self.assertTrue(invoice.is_provisional)
        self.assertEqual(invoice.billable_days, 2)
        self.assertEqual(invoice.room_charge_total, Decimal('30000.00'))

    def test_payment_updates_balances_and_invoice_status(self):
        stay = self._create_stay(
            status=GuestStay.STATUS_CHECKED_IN,
            check_in_days_ago=3,
            check_out_days_ago=None,
        )
        Sale.objects.create(
            stay=stay,
            product=self.product,
            quantity=1,
            payment_method='cash',
            recorded_by=self.manager,
            unit_price=Decimal('0.00'),
            total_amount=Decimal('0.00'),
        )
        stay.status = GuestStay.STATUS_CHECKED_OUT
        stay.check_out_date = timezone.localdate() - timedelta(days=1)
        stay.save(update_fields=['status', 'check_out_date', 'updated_at'])
        invoice = InvoiceGeneratorService.generate(stay=stay, user=self.manager)

        InvoicePaymentService.record_payment(
            invoice=invoice,
            cleaned_data={
                'payment_type': InvoicePayment.TYPE_ROOM,
                'amount': Decimal('10000.00'),
                'payment_method': 'transfer',
                'reference': 'ROOM-001',
                'notes': 'Deposit',
            },
            user=self.staff,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_PARTIALLY_PAID)

        InvoicePaymentService.record_payment(
            invoice=invoice,
            cleaned_data={
                'payment_type': InvoicePayment.TYPE_ROOM,
                'amount': Decimal('20000.00'),
                'payment_method': 'transfer',
                'reference': 'ROOM-002',
                'notes': 'Room balance',
            },
            user=self.staff,
        )
        InvoicePaymentService.record_payment(
            invoice=invoice,
            cleaned_data={
                'payment_type': InvoicePayment.TYPE_PRODUCT,
                'amount': Decimal('1000.00'),
                'payment_method': 'cash',
                'reference': 'PROD-001',
                'notes': 'Product payment',
            },
            user=self.staff,
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.total_payments, Decimal('31000.00'))
        self.assertEqual(invoice.balance, Decimal('0.00'))
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)

    def test_payment_cannot_exceed_remaining_room_balance(self):
        stay = self._create_stay()
        invoice = InvoiceGeneratorService.generate(stay=stay, user=self.manager)

        payment = InvoicePayment(
            invoice=invoice,
            payment_type=InvoicePayment.TYPE_ROOM,
            amount=Decimal('99999.00'),
            payment_method='cash',
            received_by=self.staff,
            received_by_full_name=self.staff.full_name,
            received_by_username=self.staff.email,
            received_by_role=self.staff.role,
        )

        with self.assertRaises(ValidationError):
            payment.full_clean()
