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
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
