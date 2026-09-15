from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from inventory.models import InventoryItem
from products.models import Product


class Recipe(models.Model):
    """
    A bill of materials for a single Product: what inventory items, in what
    quantities, produce `yield_quantity` units of the product. Never stores
    a copied inventory price — cost is always pulled live from the current
    batch/weighted-average cost of each ingredient.
    """
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='recipe')
    yield_quantity = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('1'))
    yield_unit = models.CharField(max_length=50, default='portion')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(yield_quantity__gt=0), name='recipe_yield_gt_zero'),
        ]

    def __str__(self):
        return f"Recipe for {self.product.name}"

    def calculate_batch_cost(self):
        """Total cost to produce one full batch (yield_quantity units), using current inventory cost."""
        total = Decimal('0')
        for ingredient in self.ingredients.select_related('inventory_item').all():
            total += ingredient.calculate_cost()
        for extra in self.extra_costs.filter(is_active=True):
            total += extra.amount
        return total

    def calculate_cost_per_unit(self):
        batch_cost = self.calculate_batch_cost()
        if not self.yield_quantity:
            return Decimal('0')
        return (batch_cost / self.yield_quantity).quantize(Decimal('0.01'))

    def cost_breakdown(self):
        """Line-by-line breakdown for the transparency/costing page."""
        lines = []
        for ingredient in self.ingredients.select_related('inventory_item').all():
            lines.append({
                'label': ingredient.inventory_item.item_name,
                'quantity': ingredient.quantity,
                'unit': ingredient.unit,
                'unit_cost': ingredient.inventory_item.weighted_average_cost,
                'cost': ingredient.calculate_cost(),
            })
        for extra in self.extra_costs.filter(is_active=True):
            lines.append({
                'label': extra.name,
                'quantity': None,
                'unit': None,
                'unit_cost': None,
                'cost': extra.amount,
            })
        return lines

     
    def get_insufficient_ingredients(self, units=1):
        """
        Which active ingredients don't currently have enough inventory to
        prepare `units` servings of this recipe right now. Empty list means
        everything needed is available - the dish can actually be cooked.
        """
        from decimal import Decimal
        portion_fraction = Decimal(units) / self.yield_quantity
        shortfalls = []
        for ingredient in self.ingredients.filter(is_active=True).select_related('inventory_item'):
            required_qty = ingredient.effective_quantity * portion_fraction
            available_qty = ingredient.inventory_item.total_batch_quantity
            if available_qty < required_qty:
                shortfalls.append({
                    'inventory_item': ingredient.inventory_item,
                    'required': required_qty,
                    'available': available_qty,
                })
        return shortfalls

    def can_prepare(self, units=1):
        return not self.get_insufficient_ingredients(units=units)	


class RecipeIngredient(models.Model):
    """
    One line of a recipe. Stores only the inventory item + quantity + unit —
    never a copied price, so cost always reflects current inventory cost.
    """
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ingredients')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='recipe_uses')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(max_length=50, help_text='Must be compatible with the inventory item\'s unit_type.')
    waste_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        help_text='Optional. Extra percentage consumed to account for prep waste, e.g. 5.00 for 5%.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='recipeingredient_quantity_gt_zero'),
        ]
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.inventory_item.item_name}"

    def clean(self):
        if self.unit and self.inventory_item_id and self.unit != self.inventory_item.unit_type:
            raise ValidationError({
                'unit': (
                    f"Unit '{self.unit}' does not match {self.inventory_item.item_name}'s "
                    f"inventory unit '{self.inventory_item.unit_type}'. Convert to the same unit "
                    f"before saving — automatic unit conversion is not supported."
                )
            })

    @property
    def effective_quantity(self):
        """Quantity required including waste allowance."""
        multiplier = Decimal('1') + (self.waste_percentage / Decimal('100'))
        return self.quantity * multiplier

    def calculate_cost(self):
        unit_cost = self.inventory_item.weighted_average_cost
        return (self.effective_quantity * unit_cost).quantize(Decimal('0.01'))


class RecipeExtraCost(models.Model):
    """
    Optional non-inventory production cost lines: cooking gas treated as
    overhead, packaging, or any other configured cost component. Kept
    generic (not gas-specific) so House IX can add whatever line items
    make sense for a given recipe.
    """
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='extra_costs')
    name = models.CharField(max_length=100, help_text='e.g. "Cooking Gas", "Takeaway Packaging"')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name='recipeextracost_amount_nonneg'),
        ]
        ordering = ['id']

    def __str__(self):
        return f"{self.name}: {self.amount}"
