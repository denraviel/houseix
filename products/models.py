from django.db import models
from decimal import Decimal


class Product(models.Model):
    CATEGORY_CHOICES = (
        ('Kitchen', 'Kitchen'),
        ('Bar', 'Bar'),
        ('Room Service', 'Room Service'),
        ('Drinks', 'Drinks'),
        ('Snacks', 'Snacks'),
        ('Others', 'Others'),
    )

    COSTING_METHOD_MANUAL = 'manual'
    COSTING_METHOD_RECIPE = 'recipe'
    COSTING_METHOD_CHOICES = (
        (COSTING_METHOD_MANUAL, 'Manual'),
        (COSTING_METHOD_RECIPE, 'Recipe / Inventory'),
    )
    
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Others')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Manual cost. Used directly when costing_method is Manual, and as a fallback if a Recipe product has no recipe configured yet.',
    )
    costing_method = models.CharField(max_length=10, choices=COSTING_METHOD_CHOICES, default=COSTING_METHOD_MANUAL)
    quantity_in_stock = models.IntegerField(default=0)
    unit_type = models.CharField(max_length=50, default='unit')
    is_available = models.BooleanField(default=True)  # Keep this as manual control
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ('name', 'category')
    
    def __str__(self):
        return self.name
    
    def can_prepare(self, units=1):
        """For recipe-costed dishes: can we actually make `units` of this
        right now, given current inventory? Manual-costed products always
        return True here (their availability is quantity_in_stock, not this)."""
        if self.costing_method != self.COSTING_METHOD_RECIPE:
            return True
        recipe = getattr(self, 'recipe', None)
        if recipe is None or not recipe.is_active or not recipe.ingredients.filter(is_active=True).exists():
            return True  # no recipe configured yet - falls back to manual cost, not ingredient-gated
        return recipe.can_prepare(units=units)

    @property
    def status(self):
        if not self.is_available:
            return "Unavailable"
        if self.costing_method == self.COSTING_METHOD_MANUAL and self.quantity_in_stock <= 0:
            return "Unavailable"
        if self.costing_method == self.COSTING_METHOD_RECIPE and not self.can_prepare(units=1):
            return "Unavailable"
        return "Available"
    
    @property
    def is_available_for_sale(self):
        """
        Recipe-costed dishes are made fresh per order from raw inventory —
        there is no finished-goods count to run out of, so availability is
        just the manual on/off toggle (e.g. staff marking a dish '86'd').
        Manual-costed products (bottled drinks, etc.) are genuinely stocked
        items, so they still require quantity_in_stock > 0.
        """
        if not self.is_available:
            return False
        if self.costing_method == self.COSTING_METHOD_MANUAL:
            return self.quantity_in_stock > 0
        return self.can_prepare(units=1)

    @property
    def current_cost(self):
        """
        The cost to use right now for margin/food-cost display. Recipe
        products fall back to cost_price only if no recipe exists yet, so
        nothing breaks while a recipe is being built.
        """
        if self.costing_method == self.COSTING_METHOD_RECIPE:
            recipe = getattr(self, 'recipe', None)
            if recipe is not None and recipe.is_active:
                return recipe.calculate_cost_per_unit()
        return self.cost_price

    @property
    def gross_profit(self):
        return self.selling_price - self.current_cost

    @property
    def food_cost_percentage(self):
        if not self.selling_price:
            return Decimal('0')
        return (self.current_cost / self.selling_price * 100).quantize(Decimal('0.01'))
