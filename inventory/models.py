
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class InventoryItem(models.Model):
    CATEGORY_CHOICES = (
        ('Kitchen', 'Kitchen'),
        ('Bar', 'Bar'),
        ('Cleaning', 'Cleaning'),
        ('Room Supplies', 'Room Supplies'),
        ('Food Items', 'Food Items'),
        ('Others', 'Others'),
    )
    
    item_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Others')
    quantity = models.IntegerField()
    unit_type = models.CharField(max_length=50)  # e.g., 'pieces', 'kg', 'liters'
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    low_stock_threshold = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_updated']
        unique_together = ('item_name', 'category')
    
    def __str__(self):
        return self.item_name

    @property
    def total_batch_quantity(self):
        return self.batches.filter(quantity_remaining__gt=0).aggregate(
            total=models.Sum('quantity_remaining')
        )['total'] or Decimal('0')

    @property
    def total_inventory_value(self):
        total = Decimal('0')
        for batch in self.batches.filter(quantity_remaining__gt=0):
            total += batch.quantity_remaining * batch.unit_cost
        return total

    @property
    def weighted_average_cost(self):
        qty = self.total_batch_quantity
        if not qty:
            return Decimal('0')
        return (self.total_inventory_value / qty).quantize(Decimal('0.01'))

    @property
    def latest_purchase_cost(self):
        latest_batch = self.batches.order_by('-purchased_at', '-id').first()
        return latest_batch.unit_cost if latest_batch else self.cost_price

    @property
    def active_batch_count(self):
        return self.batches.filter(quantity_remaining__gt=0).count()


class StockBatch(models.Model):
    """
    A single purchase/receipt of an inventory item at a specific cost.
    Immutable once created except for quantity_remaining, which only
    decreases as consumption happens against it (FIFO order).
    """
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='batches')
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_remaining = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    supplier = models.CharField(max_length=255, blank=True)
    purchased_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_batches_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_opening_balance = models.BooleanField(
        default=False,
        help_text='True for the batch auto-created from pre-existing stock when this system was introduced.',
    )

    class Meta:
        ordering = ['purchased_at', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_received__gte=0), name='stockbatch_quantity_received_nonneg'),
            models.CheckConstraint(condition=models.Q(quantity_remaining__gte=0), name='stockbatch_quantity_remaining_nonneg'),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name='stockbatch_unit_cost_nonneg'),
        ]

    def __str__(self):
        return f"{self.item.item_name} batch #{self.pk} ({self.quantity_remaining}/{self.quantity_received} @ {self.unit_cost})"

    @property
    def total_cost(self):
        return self.quantity_received * self.unit_cost

    @property
    def remaining_value(self):
        return self.quantity_remaining * self.unit_cost


class InventoryTransaction(models.Model):
    TYPE_PURCHASE = 'purchase'
    TYPE_SALE_CONSUMPTION = 'sale_consumption'
    TYPE_RECIPE_CONSUMPTION = 'recipe_consumption'
    TYPE_WASTAGE = 'wastage'
    TYPE_ADJUSTMENT = 'adjustment'
    TYPE_TRANSFER = 'transfer'
    TYPE_MANUAL_TAKE = 'manual_take'

    TYPE_CHOICES = [
        (TYPE_PURCHASE, 'Purchase'),
        (TYPE_SALE_CONSUMPTION, 'Sale Consumption'),
        (TYPE_RECIPE_CONSUMPTION, 'Recipe Consumption'),
        (TYPE_WASTAGE, 'Wastage'),
        (TYPE_ADJUSTMENT, 'Adjustment'),
        (TYPE_TRANSFER, 'Transfer'),
        (TYPE_MANUAL_TAKE, 'Manual Stock Take'),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    batch = models.ForeignKey(StockBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, help_text='Positive for additions, negative for consumption/wastage.')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=255, blank=True, help_text='e.g. Sale #123, Recipe: Fried Rice')
    reason = models.TextField(blank=True)
    recipe = models.ForeignKey(
        'recipes.Recipe', on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_transactions',
        help_text='The recipe/dish that caused this consumption, if any.',
    )
    sale = models.ForeignKey(
        'sales.Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_transactions',
        help_text='The specific order/sale that caused this movement, if any.',
    )
    previous_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="This item's total stock across all batches immediately before this transaction.",
    )
    new_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="This item's total stock across all batches immediately after this transaction.",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.quantity} {self.item.unit_type} of {self.item.item_name}"


class StockMovement(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_taken = models.IntegerField()
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    taken_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity_taken} {self.item.unit_type} of {self.item.item_name} taken by {self.taken_by.full_name}"

