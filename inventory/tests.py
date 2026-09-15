from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import InventoryItem, InventoryTransaction, StockBatch
from .services import InsufficientStockError, InventoryBatchService


class BatchCostingTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.user = self.UserModel.objects.create_user(
            email='stockuser@example.com',
            password='Password@123',
            full_name='Stock User',
            phone_number='08000000201',
            username='stock.user',
            role='manager',
            is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(
            item_name='Rice', category='Kitchen', quantity=0, unit_type='kg', cost_price=0,
        )

    def test_add_stock_creates_a_batch(self):
        InventoryBatchService.add_stock(
            item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user,
        )
        self.assertEqual(StockBatch.objects.filter(item=self.rice).count(), 1)
        batch = StockBatch.objects.get(item=self.rice)
        self.assertEqual(batch.quantity_remaining, Decimal('10'))
        self.assertEqual(batch.unit_cost, Decimal('2000'))
        self.assertEqual(
            InventoryTransaction.objects.filter(item=self.rice, transaction_type='purchase').count(), 1
        )

    def test_second_purchase_does_not_overwrite_first_batch(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2500'), user=self.user)

        batches = list(StockBatch.objects.filter(item=self.rice).order_by('purchased_at', 'id'))
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0].unit_cost, Decimal('2000'))
        self.assertEqual(batches[1].unit_cost, Decimal('2500'))

    def test_total_quantity_value_and_weighted_average(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2500'), user=self.user)

        self.assertEqual(self.rice.total_batch_quantity, Decimal('20'))
        self.assertEqual(self.rice.total_inventory_value, Decimal('45000'))
        self.assertEqual(self.rice.weighted_average_cost, Decimal('2250.00'))

    def test_fifo_consumes_oldest_batch_first(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2500'), user=self.user)

        consumed = InventoryBatchService.consume(
            item=self.rice, quantity=Decimal('6'),
            transaction_type=InventoryTransaction.TYPE_RECIPE_CONSUMPTION, user=self.user,
        )
        self.assertEqual(len(consumed), 1)
        batch, qty, unit_cost = consumed[0]
        self.assertEqual(qty, Decimal('6'))
        self.assertEqual(unit_cost, Decimal('2000'))

        batches = list(StockBatch.objects.filter(item=self.rice).order_by('purchased_at', 'id'))
        self.assertEqual(batches[0].quantity_remaining, Decimal('4'))
        self.assertEqual(batches[1].quantity_remaining, Decimal('10'))

    def test_cross_batch_consumption_when_old_batch_insufficient(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('4'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2500'), user=self.user)

        consumed = InventoryBatchService.consume(
            item=self.rice, quantity=Decimal('6'),
            transaction_type=InventoryTransaction.TYPE_RECIPE_CONSUMPTION, user=self.user,
        )
        self.assertEqual(len(consumed), 2)
        total_cost = sum(qty * unit_cost for _batch, qty, unit_cost in consumed)
        self.assertEqual(total_cost, Decimal('13000'))  # 4*2000 + 2*2500

        batches = list(StockBatch.objects.filter(item=self.rice).order_by('purchased_at', 'id'))
        self.assertEqual(batches[0].quantity_remaining, Decimal('0'))
        self.assertEqual(batches[1].quantity_remaining, Decimal('8'))

    def test_insufficient_stock_raises_and_does_not_mutate_batches(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('4'), unit_cost=Decimal('2000'), user=self.user)

        with self.assertRaises(InsufficientStockError):
            InventoryBatchService.consume(
                item=self.rice, quantity=Decimal('10'),
                transaction_type=InventoryTransaction.TYPE_RECIPE_CONSUMPTION, user=self.user,
            )
        batch = StockBatch.objects.get(item=self.rice)
        self.assertEqual(batch.quantity_remaining, Decimal('4'))  # unchanged - rolled back

    def test_price_change_does_not_affect_old_batch(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user)
        batch_1 = StockBatch.objects.get(item=self.rice)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('20'), unit_cost=Decimal('3000'), user=self.user)

        batch_1.refresh_from_db()
        self.assertEqual(batch_1.unit_cost, Decimal('2000'))
        self.assertEqual(StockBatch.objects.filter(item=self.rice).count(), 2)

    def test_wastage_reduces_stock_and_records_reason(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.record_wastage(item=self.rice, quantity=Decimal('2'), user=self.user, reason='Spoiled')

        self.assertEqual(self.rice.total_batch_quantity, Decimal('8'))
        txn = InventoryTransaction.objects.filter(item=self.rice, transaction_type='wastage').first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.reason, 'Spoiled')
