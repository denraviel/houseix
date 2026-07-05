from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = (
        ('Kitchen', 'Kitchen'),
        ('Bar', 'Bar'),
        ('Room Service', 'Room Service'),
        ('Drinks', 'Drinks'),
        ('Snacks', 'Snacks'),
        ('Others', 'Others'),
    )
    
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Others')
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
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
    
    @property
    def status(self):
        if self.quantity_in_stock <= 0 or not self.is_available:
            return "Unavailable"
        return "Available"
    
    @property
    def is_available_for_sale(self):
        return self.quantity_in_stock > 0 and self.is_available
