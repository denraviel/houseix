from django.db import models
from django.conf import settings


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


class StockMovement(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity_taken = models.IntegerField()
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    taken_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.quantity_taken} {self.item.unit_type} of {self.item.item_name} taken by {self.taken_by.full_name}"
