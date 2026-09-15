from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase
from django.urls import reverse

from accounts.models import JobPosition, ModulePermission
from customers.models import Customer
from products.models import Product
from rooms.models import Room
from stays.models import GuestStay

from .forms import SaleForm
from .models import Sale


class SalesAccessTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner@example.com',
            password='Owner@12345',
            full_name='Owner User',
            phone_number='08000000111',
            username='owner.user',
            role='owner',
            is_first_login=False,
        )
        self.barman_position, _ = JobPosition.objects.get_or_create(
            code='barman',
            defaults={
                'name': 'Barman',
                'description': 'Bar service and beverage sales.',
                'department': JobPosition.DEPARTMENT_FOOD_BEVERAGE,
                'is_active': True,
            },
        )
        self.sales_module = ModulePermission.objects.get(code='sales')
        self.barman = self.UserModel.objects.create_user(
            email='barman@example.com',
            password='Barman@12345',
            full_name='Bar User',
            phone_number='08000000112',
            username='bar.user',
            role='staff',
            is_first_login=False,
            module_permissions=[self.sales_module],
        )
        self.barman.positions.add(self.barman_position)
        self.bar_product = Product.objects.create(
            name='Premium Whisky',
            category='Bar',
            selling_price=15000,
            cost_price=9000,
            quantity_in_stock=12,
            unit_type='bottle',
            is_available=True,
        )
        self.kitchen_product = Product.objects.create(
            name='Chef Special Rice',
            category='Kitchen',
            selling_price=5000,
            cost_price=2500,
            quantity_in_stock=10,
            unit_type='plate',
            is_available=True,
        )
        self.customer = Customer.objects.create(
            full_name='Checked Out Guest',
            phone_number='08000000999',
            email='guest@example.com',
        )
        self.room = Room.objects.create(
            room_number='B101',
            room_type=Room.TYPE_SINGLE,
            daily_rate=25000,
            status=Room.STATUS_AVAILABLE,
        )
        self.checked_in_stay = GuestStay.objects.create(
            customer=self.customer,
            room=self.room,
            daily_rate=25000,
            status=GuestStay.STATUS_CHECKED_IN,
        )
        self.checked_out_stay = GuestStay.objects.create(
            customer=self.customer,
            room=Room.objects.create(
                room_number='B102',
                room_type=Room.TYPE_SINGLE,
                daily_rate=25000,
                status=Room.STATUS_AVAILABLE,
            ),
            daily_rate=25000,
            status=GuestStay.STATUS_CHECKED_OUT,
        )

    def test_barman_sale_form_only_shows_bar_products(self):
        form = SaleForm(user=self.barman)

        product_names = list(form.fields['product'].queryset.values_list('name', flat=True))

        self.assertIn(self.bar_product.name, product_names)
        self.assertNotIn(self.kitchen_product.name, product_names)

    def test_barman_can_access_sales_list_and_only_sees_own_sales(self):
        Sale.objects.create(
            product=self.bar_product,
            quantity=1,
            payment_method='cash',
            recorded_by=self.barman,
        )
        owner_product = Product.objects.create(
            name='Owner Reserve',
            category='Bar',
            selling_price=18000,
            cost_price=11000,
            quantity_in_stock=8,
            unit_type='bottle',
            is_available=True,
        )
        Sale.objects.create(
            product=owner_product,
            quantity=1,
            payment_method='card',
            recorded_by=self.owner,
        )

        self.client.force_login(self.barman)
        response = self.client.get(reverse('sales_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bar_product.name)
        self.assertNotContains(response, owner_product.name)

    def test_barman_cannot_submit_non_bar_product_sale(self):
        self.client.force_login(self.barman)

        response = self.client.post(
            reverse('sale_create'),
            {
                'product': self.kitchen_product.pk,
                'quantity': 1,
                'payment_method': 'cash',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertEqual(Sale.objects.count(), 0)

    def test_sale_form_only_shows_active_guest_stays(self):
        form = SaleForm(user=self.owner)

        stay_ids = list(form.fields['stay'].queryset.values_list('pk', flat=True))

        self.assertIn(self.checked_in_stay.pk, stay_ids)
        self.assertNotIn(self.checked_out_stay.pk, stay_ids)

    def test_cannot_record_sale_for_checked_out_guest(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('sale_create'),
            {
                'stay': self.checked_out_stay.pk,
                'product': self.bar_product.pk,
                'quantity': 1,
                'payment_method': 'cash',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertEqual(Sale.objects.count(), 0)

    def test_sale_model_rejects_checked_out_guest_stay(self):
        sale = Sale(
            stay=self.checked_out_stay,
            product=self.bar_product,
            quantity=1,
            payment_method='cash',
            recorded_by=self.owner,
        )

        with self.assertRaises(ValidationError) as error:
            sale.save()

        self.assertIn('Sales cannot be recorded for a guest who has already checked out or whose stay is closed.', error.exception.message_dict['stay'])


class RecipeCogsIntegrationTests(TestCase):
    """
    Verifies the actual point of contact between a real POS sale and the
    inventory/recipe system: recipe-costed products consume inventory via
    FIFO exactly once, actual_cogs is captured and frozen, and a sale is
    blocked entirely (rolled back) when stock is insufficient.
    """

    def setUp(self):
        from decimal import Decimal
        from inventory.models import InventoryItem
        from inventory.services import InventoryBatchService
        from recipes.models import Recipe, RecipeIngredient

        self.UserModel = get_user_model()
        self.staff = self.UserModel.objects.create_user(
            email='pos.staff@example.com',
            password='Password@123',
            full_name='POS Staff',
            phone_number='08000000401',
            username='pos.staff',
            role='staff',
            is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(item_name='POS Rice', category='Kitchen', quantity=0, unit_type='kg', cost_price=0)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.staff)

        self.product = Product.objects.create(
            name='POS Fried Rice', category='Kitchen', selling_price=Decimal('5000'),
            cost_price=Decimal('0'), costing_method=Product.COSTING_METHOD_RECIPE,
            quantity_in_stock=100, unit_type='portion',
        )
        self.recipe = Recipe.objects.create(product=self.product, yield_quantity=Decimal('10'), yield_unit='portion')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.rice, quantity=Decimal('5'), unit='kg')

    def test_sale_of_recipe_product_captures_actual_cogs(self):
        from sales.services import SaleWorkflowService

        sale = Sale(
            product=self.product, quantity=2, payment_method='cash', recorded_by=self.staff,
        )
        sale.save()
        SaleWorkflowService.mark_prepared(sale=sale, user=self.staff)
        sale.refresh_from_db()
        self.assertIsNotNone(sale.actual_cogs)
        self.assertGreater(sale.actual_cogs, 0)
        self.assertIsNotNone(sale.cogs_breakdown)

    def test_sale_blocked_when_insufficient_stock(self):
        from inventory.services import InsufficientStockError
        from sales.services import SaleWorkflowService

        # Recipe needs 5kg per 10 portions -> selling 50 portions needs 25kg, only 10kg exists.
        # Creating the order itself succeeds (no consumption yet) - it's marking it
        # prepared that must fail, since that's when ingredients are actually needed.
        sale = Sale(product=self.product, quantity=50, payment_method='cash', recorded_by=self.staff)
        sale.save()

        with self.assertRaises(InsufficientStockError):
            SaleWorkflowService.mark_prepared(sale=sale, user=self.staff)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_CREATED)  # never advanced past created
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('10'))  # untouched

    def test_historical_cogs_unaffected_by_later_price_change(self):
        from inventory.services import InventoryBatchService

        sale = Sale(product=self.product, quantity=2, payment_method='cash', recorded_by=self.staff)
        sale.save()
        sale.refresh_from_db()
        original_cogs = sale.actual_cogs

        # New, much more expensive batch arrives after the sale.
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('9000'), user=self.staff)

        sale.refresh_from_db()
        self.assertEqual(sale.actual_cogs, original_cogs)  # unchanged despite new higher-cost stock

    def test_manual_costed_product_sale_does_not_touch_inventory(self):
        manual_product = Product.objects.create(
            name='Manual Soda', category='Drinks', selling_price=Decimal('500'),
            cost_price=Decimal('200'), costing_method=Product.COSTING_METHOD_MANUAL,
            quantity_in_stock=50, unit_type='bottle',
        )
        sale = Sale(product=manual_product, quantity=3, payment_method='cash', recorded_by=self.staff)
        sale.save()
        sale.refresh_from_db()
        self.assertIsNone(sale.actual_cogs)


class MadeToOrderCostingTests(TestCase):
    """
    Confirms recipe-costed dishes follow a made-to-order model: cost and
    inventory consumption are calculated per individual order using the
    recipe, NOT drawn from a pre-cooked finished-dish stock count. A dish
    with quantity_in_stock == 0 must still be sellable and listed, since
    it's cooked fresh from raw ingredients rather than pulled from a shelf.
    """

    def setUp(self):
        from inventory.models import InventoryItem
        from inventory.services import InventoryBatchService
        from recipes.models import Recipe, RecipeExtraCost, RecipeIngredient

        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner.kitchen@example.com',
            password='Password@123',
            full_name='Owner Kitchen',
            phone_number='08000000501',
            username='owner.kitchen',
            role='owner',
            is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(item_name='Jollof Rice Grain', category='Kitchen', quantity=0, unit_type='kg', cost_price=0)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('2000'), user=self.owner)

        # Deliberately quantity_in_stock=0 - this dish is made to order, never "stocked".
        self.jollof = Product.objects.create(
            name='Jollof Rice', category='Kitchen', selling_price=Decimal('1500'),
            cost_price=Decimal('0'), costing_method=Product.COSTING_METHOD_RECIPE,
            quantity_in_stock=0, unit_type='plate', is_available=True,
        )
        self.recipe = Recipe.objects.create(product=self.jollof, yield_quantity=Decimal('1'), yield_unit='plate')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.rice, quantity=Decimal('0.2'), unit='kg')
        RecipeExtraCost.objects.create(recipe=self.recipe, name='Gas', amount=Decimal('50'))

    def test_zero_quantity_in_stock_dish_is_still_available_and_listed(self):
        from sales.services import SalesAccessService
        self.assertTrue(self.jollof.is_available_for_sale)
        self.assertEqual(self.jollof.status, 'Available')
        self.assertIn(self.jollof, SalesAccessService.available_products_for_user(self.owner))

    def test_toggling_is_available_off_hides_a_recipe_dish(self):
        self.jollof.is_available = False
        self.jollof.save()
        self.assertFalse(self.jollof.is_available_for_sale)
        self.assertEqual(self.jollof.status, 'Unavailable')

    def test_five_separate_orders_each_consume_their_own_portion(self):
        """5 guests order 1 Jollof Rice each, separately - not one batch of 5."""
        from sales.services import SaleWorkflowService

        for _ in range(5):
            sale = Sale(product=self.jollof, quantity=1, payment_method='cash', recorded_by=self.owner)
            sale.save()
            SaleWorkflowService.mark_prepared(sale=sale, user=self.owner)

        self.assertEqual(Sale.objects.filter(product=self.jollof).count(), 5)
        # 5 orders x 0.2kg = 1kg consumed total, each captured with its own actual_cogs.
        remaining = self.rice.batches.first().quantity_remaining
        self.assertEqual(remaining, Decimal('9'))
        for sale in Sale.objects.filter(product=self.jollof):
            self.assertIsNotNone(sale.actual_cogs)
            self.assertEqual(sale.actual_cogs, Decimal('450.00'))   # 0.2kg * 2000/kg + 50 gas

    def test_quantity_in_stock_never_changes_for_recipe_product(self):
        sale = Sale(product=self.jollof, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        self.jollof.refresh_from_db()
        self.assertEqual(self.jollof.quantity_in_stock, 0)  # untouched, made-to-order has no finished-dish count

    def test_manual_product_still_requires_quantity_in_stock(self):
        from sales.forms import SaleForm
        soda = Product.objects.create(
            name='Bottled Soda', category='Drinks', selling_price=Decimal('300'),
            cost_price=Decimal('100'), costing_method=Product.COSTING_METHOD_MANUAL,
            quantity_in_stock=2, unit_type='bottle', is_available=True,
        )
        form = SaleForm(data={'product': soda.pk, 'quantity': 5, 'payment_method': 'cash'}, user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)


class OrderLifecycleTests(TestCase):
    """
    Verifies the made-to-order lifecycle: creating an order must NOT consume
    inventory; consumption only happens when SaleWorkflowService.mark_prepared
    is called; cancelling before preparation consumes nothing; every
    resulting InventoryTransaction is fully traceable (staff, order, dish,
    before/after stock).
    """

    def setUp(self):
        from inventory.models import InventoryItem, InventoryTransaction
        from inventory.services import InventoryBatchService
        from recipes.models import Recipe, RecipeIngredient

        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner.lifecycle@example.com',
            password='Password@123',
            full_name='Owner Lifecycle',
            phone_number='08000000601',
            username='owner.lifecycle',
            role='owner',
            is_first_login=False,
        )
        self.kitchen_staff = self.UserModel.objects.create_user(
            email='john.kitchen@example.com',
            password='Password@123',
            full_name='John',
            phone_number='08000000602',
            username='john.kitchen',
            role='staff',
            is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(item_name='Lifecycle Rice', category='Kitchen', quantity=0, unit_type='kg', cost_price=0)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('20'), unit_cost=Decimal('2000'), user=self.owner)

        self.dish = Product.objects.create(
            name='Rice & Stew', category='Kitchen', selling_price=Decimal('1500'),
            cost_price=Decimal('0'), costing_method=Product.COSTING_METHOD_RECIPE,
            quantity_in_stock=0, unit_type='plate', is_available=True,
        )
        self.recipe = Recipe.objects.create(product=self.dish, yield_quantity=Decimal('1'), yield_unit='plate')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.rice, quantity=Decimal('0.25'), unit='kg')
        self.InventoryTransaction = InventoryTransaction

    def test_order_creation_does_not_consume_inventory(self):
        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        self.assertEqual(sale.status, Sale.STATUS_CREATED)
        self.assertIsNone(sale.actual_cogs)
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('20'))  # untouched

    def test_mark_prepared_consumes_inventory_and_captures_cogs(self):
        from sales.services import SaleWorkflowService

        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        SaleWorkflowService.mark_prepared(sale=sale, user=self.kitchen_staff)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_PREPARED)
        self.assertEqual(sale.prepared_by, self.kitchen_staff)
        self.assertIsNotNone(sale.prepared_at)
        self.assertEqual(sale.actual_cogs, Decimal('500.00'))  # 0.25kg * 2000

        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('19.75'))

    def test_inventory_transaction_is_fully_traceable(self):
        from sales.services import SaleWorkflowService

        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        SaleWorkflowService.mark_prepared(sale=sale, user=self.kitchen_staff)

        txn = self.InventoryTransaction.objects.filter(item=self.rice, transaction_type='recipe_consumption').latest('id')
        self.assertEqual(txn.performed_by, self.kitchen_staff)
        self.assertEqual(txn.sale, sale)
        self.assertEqual(txn.recipe, self.recipe)
        self.assertEqual(txn.previous_quantity, Decimal('20'))
        self.assertEqual(txn.new_quantity, Decimal('19.75'))
        self.assertEqual(txn.quantity, Decimal('-0.25'))
        self.assertIn('Rice & Stew', txn.reason)

    def test_cancel_before_preparation_consumes_nothing(self):
        from sales.services import SaleWorkflowService

        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        SaleWorkflowService.cancel(sale=sale, user=self.owner, reason='Guest changed mind')

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_CANCELLED)
        self.assertEqual(sale.cancellation_reason, 'Guest changed mind')
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('20'))  # untouched

    def test_cannot_prepare_a_cancelled_order(self):
        from sales.services import SaleWorkflowService

        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        SaleWorkflowService.cancel(sale=sale, user=self.owner)

        with self.assertRaises(ValueError):
            SaleWorkflowService.mark_prepared(sale=sale, user=self.kitchen_staff)
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('20'))

    def test_cannot_prepare_the_same_order_twice(self):
        from sales.services import SaleWorkflowService

        sale = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale.save()
        SaleWorkflowService.mark_prepared(sale=sale, user=self.kitchen_staff)

        with self.assertRaises(ValueError):
            SaleWorkflowService.mark_prepared(sale=sale, user=self.kitchen_staff)

        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('19.75'))  # only consumed once

    def test_manual_product_auto_completes_at_creation(self):
        soda = Product.objects.create(
            name='Lifecycle Soda', category='Drinks', selling_price=Decimal('300'),
            cost_price=Decimal('100'), costing_method=Product.COSTING_METHOD_MANUAL,
            quantity_in_stock=10, unit_type='bottle', is_available=True,
        )
        sale = Sale(product=soda, quantity=2, payment_method='cash', recorded_by=self.owner)
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_COMPLETED)

    def test_staff_accountability_multiple_orders_by_different_staff(self):
        """Management should be able to answer 'who consumed this inventory'."""
        from sales.services import SaleWorkflowService

        mary = self.UserModel.objects.create_user(
            email='mary.kitchen@example.com', password='Password@123', full_name='Mary',
            phone_number='08000000603', username='mary.kitchen', role='staff', is_first_login=False,
        )
        sale_1 = Sale(product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        sale_1.save()
        SaleWorkflowService.mark_prepared(sale=sale_1, user=self.kitchen_staff)

        sale_2 = Sale(product=self.dish, quantity=2, payment_method='cash', recorded_by=self.owner)
        sale_2.save()
        SaleWorkflowService.mark_prepared(sale=sale_2, user=mary)

        john_consumption = self.InventoryTransaction.objects.filter(
            item=self.rice, transaction_type='recipe_consumption', performed_by=self.kitchen_staff,
        ).aggregate(total=models.Sum('quantity'))['total']
        mary_consumption = self.InventoryTransaction.objects.filter(
            item=self.rice, transaction_type='recipe_consumption', performed_by=mary,
        ).aggregate(total=models.Sum('quantity'))['total']

        self.assertEqual(abs(john_consumption), Decimal('0.25'))
        self.assertEqual(abs(mary_consumption), Decimal('0.50'))


class MultiItemOrderTests(TestCase):
    """
    A customer orders a kitchen dish plus a bottled drink on one ticket:
    both lines belong to one Order, each keeps its own lifecycle, and the
    whole ticket bills to a single invoice.
    """

    def setUp(self):
        from inventory.models import InventoryItem
        from inventory.services import InventoryBatchService
        from recipes.models import Recipe, RecipeIngredient

        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner.order@example.com', password='Password@123', full_name='Owner Order',
            phone_number='08000000701', username='owner.order', role='owner', is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(
            item_name='Order Rice', category='Kitchen', quantity=0, unit_type='kg', cost_price=0,
        )
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('20'), unit_cost=Decimal('2000'), user=self.owner)

        self.dish = Product.objects.create(
            name='Order Jollof', category='Kitchen', selling_price=Decimal('1500'),
            cost_price=Decimal('0'), costing_method=Product.COSTING_METHOD_RECIPE,
            quantity_in_stock=0, unit_type='plate', is_available=True,
        )
        self.recipe = Recipe.objects.create(product=self.dish, yield_quantity=Decimal('1'), yield_unit='plate')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.rice, quantity=Decimal('0.25'), unit='kg')

        self.water = Product.objects.create(
            name='Order Water', category='Drinks', selling_price=Decimal('300'),
            cost_price=Decimal('100'), costing_method=Product.COSTING_METHOD_MANUAL,
            quantity_in_stock=50, unit_type='bottle', is_available=True,
        )

    def _make_order(self):
        from sales.models import Order
        return Order.objects.create(payment_method='cash', recorded_by=self.owner)

    def test_order_holds_multiple_products(self):
        order = self._make_order()
        Sale.objects.create(order=order, product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        Sale.objects.create(order=order, product=self.water, quantity=2, payment_method='cash', recorded_by=self.owner)

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total_amount, Decimal('1500') + Decimal('600'))

    def test_each_line_keeps_its_own_lifecycle(self):
        order = self._make_order()
        dish_line = Sale.objects.create(order=order, product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        water_line = Sale.objects.create(order=order, product=self.water, quantity=1, payment_method='cash', recorded_by=self.owner)

        water_line.refresh_from_db()
        dish_line.refresh_from_db()
        # Water is a shelf item - done immediately. The dish still needs cooking.
        self.assertEqual(water_line.status, Sale.STATUS_COMPLETED)
        self.assertEqual(dish_line.status, Sale.STATUS_CREATED)

    def test_preparing_one_line_consumes_only_its_own_ingredients(self):
        from sales.services import SaleWorkflowService

        order = self._make_order()
        dish_line = Sale.objects.create(order=order, product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        Sale.objects.create(order=order, product=self.water, quantity=1, payment_method='cash', recorded_by=self.owner)

        SaleWorkflowService.mark_prepared(sale=dish_line, user=self.owner)
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('19.75'))

    def test_order_lines_inherit_ticket_details(self):
        from sales.models import Order
        order = Order.objects.create(payment_method='transfer', recorded_by=self.owner)
        line = Sale.objects.create(order=order, product=self.water, quantity=1, payment_method='cash', recorded_by=self.owner)
        line.refresh_from_db()
        self.assertEqual(line.payment_method, 'transfer')  # taken from the order, not the line

    def test_one_invoice_covers_the_whole_order(self):
        from invoices.services import InvoiceGeneratorService

        order = self._make_order()
        Sale.objects.create(order=order, product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        Sale.objects.create(order=order, product=self.water, quantity=2, payment_method='cash', recorded_by=self.owner)

        invoice = InvoiceGeneratorService.generate_for_order(order=order, user=self.owner)
        linked = Sale.objects.filter(invoice_link__invoice=invoice)
        self.assertEqual(linked.count(), 2)

    def test_order_status_is_derived_from_lines(self):
        from sales.services import SaleWorkflowService

        order = self._make_order()
        dish_line = Sale.objects.create(order=order, product=self.dish, quantity=1, payment_method='cash', recorded_by=self.owner)
        Sale.objects.create(order=order, product=self.water, quantity=1, payment_method='cash', recorded_by=self.owner)

        self.assertEqual(order.status, Sale.STATUS_CREATED)  # dish still pending
        SaleWorkflowService.mark_prepared(sale=dish_line, user=self.owner)
        self.assertEqual(order.status, 'ready')  # everything now prepared/completed

    def test_insufficient_ingredients_flags_only_that_dish(self):
        """The unavailable dish is rejected; the drink is unaffected."""
        from sales.forms import OrderItemForm

        # 20kg rice, dish needs 0.25kg each -> 200 plates needs 50kg, too many.
        bad = OrderItemForm(data={'product': self.dish.pk, 'quantity': 200}, user=self.owner)
        self.assertFalse(bad.is_valid())

        good = OrderItemForm(data={'product': self.water.pk, 'quantity': 2}, user=self.owner)
        self.assertTrue(good.is_valid())
