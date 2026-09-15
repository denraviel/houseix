from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import InventoryItem
from inventory.services import InventoryBatchService
from products.models import Product

from .models import Recipe, RecipeExtraCost, RecipeIngredient
from .services import RecipeProductionService


class RecipeCostingTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.user = self.UserModel.objects.create_user(
            email='chef@example.com',
            password='Password@123',
            full_name='Chef User',
            phone_number='08000000301',
            username='chef.user',
            role='manager',
            is_first_login=False,
        )
        self.rice = InventoryItem.objects.create(item_name='Rice', category='Kitchen', quantity=0, unit_type='kg', cost_price=0)
        self.oil = InventoryItem.objects.create(item_name='Oil', category='Kitchen', quantity=0, unit_type='L', cost_price=0)
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('20'), unit_cost=Decimal('2000'), user=self.user)
        InventoryBatchService.add_stock(item=self.oil, quantity=Decimal('10'), unit_cost=Decimal('3500'), user=self.user)

        self.product = Product.objects.create(
            name='Fried Rice', category='Kitchen', selling_price=Decimal('5000'),
            cost_price=Decimal('0'), costing_method=Product.COSTING_METHOD_RECIPE,
            quantity_in_stock=100, unit_type='portion',
        )
        self.recipe = Recipe.objects.create(product=self.product, yield_quantity=Decimal('10'), yield_unit='portion')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.rice, quantity=Decimal('5'), unit='kg')
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.oil, quantity=Decimal('1'), unit='L')
        RecipeExtraCost.objects.create(recipe=self.recipe, name='Cooking Gas', amount=Decimal('960'))

    def test_recipe_batch_cost_and_per_unit(self):
        # 5kg*2000 + 1L*3500 + 960 gas = 10000 + 3500 + 960 = 14460, / 10 portions = 1446
        self.assertEqual(self.recipe.calculate_batch_cost(), Decimal('14460'))
        self.assertEqual(self.recipe.calculate_cost_per_unit(), Decimal('1446.00'))

    def test_product_current_cost_uses_recipe(self):
        self.assertEqual(self.product.current_cost, Decimal('1446.00'))
        self.assertEqual(self.product.gross_profit, Decimal('5000') - Decimal('1446.00'))

    def test_recipe_cost_updates_when_inventory_price_changes(self):
        InventoryBatchService.add_stock(item=self.rice, quantity=Decimal('10'), unit_cost=Decimal('4000'), user=self.user)
        # weighted average for rice now: (20*2000 + 10*4000) / 30 = 2666.67
        new_cost = self.recipe.calculate_cost_per_unit()
        self.assertNotEqual(new_cost, Decimal('1446.00'))

    def test_waste_percentage_increases_effective_quantity(self):
        ingredient = self.recipe.ingredients.get(inventory_item=self.rice)
        ingredient.waste_percentage = Decimal('10')
        ingredient.save()
        self.assertEqual(ingredient.effective_quantity, Decimal('5.5'))

    def test_consume_for_sale_uses_fifo_and_returns_cogs(self):
        cogs, breakdown = RecipeProductionService.consume_for_sale(
            recipe=self.recipe, units_sold=5, user=self.user, reference='Sale test',
        )
        # Half a batch: 2.5kg rice, 0.5L oil, half gas share
        remaining_rice = self.rice.batches.first().quantity_remaining
        self.assertEqual(remaining_rice, Decimal('17.5'))
        self.assertGreater(cogs, Decimal('0'))
        self.assertTrue(len(breakdown) >= 2)

    def test_manual_costing_method_ignores_recipe(self):
        self.product.costing_method = Product.COSTING_METHOD_MANUAL
        self.product.cost_price = Decimal('2000')
        self.product.save()
        self.assertEqual(self.product.current_cost, Decimal('2000'))

    def test_recipe_falls_back_to_manual_cost_if_inactive(self):
        self.recipe.is_active = False
        self.recipe.save()
        self.product.cost_price = Decimal('1800')
        self.product.save()
        self.assertEqual(self.product.current_cost, Decimal('1800'))
