from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from products.models import Product
from customers.models import Customer
from rooms.models import Room
from stays.models import GuestStay
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver


class Sale(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile Payment'),
        ('transfer', 'Bank Transfer'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    stay = models.ForeignKey(GuestStay, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.stay_id and self.stay and self.stay.is_closed:
            raise ValidationError({'stay': 'Sales cannot be recorded for a guest who has already checked out or whose stay is closed.'})
    
    def save(self, *args, **kwargs):
        if self.stay_id:
            self.customer = self.stay.customer
            self.room = self.stay.room
        if self.product:
            self.unit_price = self.product.selling_price
            self.total_amount = self.quantity * self.unit_price
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


@receiver(post_save, sender=Sale)
def reduce_product_stock(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        product.quantity_in_stock -= instance.quantity
        product.save()


@receiver(pre_delete, sender=Sale)
def restore_product_stock(sender, instance, **kwargs):
    product = instance.product
    product.quantity_in_stock += instance.quantity
    product.save()
