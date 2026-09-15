from decimal import Decimal

from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from products.models import Product
from customers.models import Customer
from rooms.models import Room
from stays.models import GuestStay
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver


class Order(models.Model):
    """
    A single customer ticket that can hold several Sale line items - e.g.
    one plate of jollof rice plus a bottle of water, ordered together,
    billed on one invoice. What's shared across the whole ticket lives
    here; per-item status stays on each Sale, because a kitchen dish and a
    bottled drink move through completely different lifecycles.
    """
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile Payment'),
        ('transfer', 'Bank Transfer'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    stay = models.ForeignKey(GuestStay, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk}"

    @property
    def total_amount(self):
        return sum(
            (line.total_amount for line in self.items.exclude(status=Sale.STATUS_CANCELLED)),
            Decimal('0.00'),
        )

    @property
    def status(self):
        """Derived from the line items rather than stored, so it can never
        drift out of sync with what the kitchen has actually done."""
        lines = list(self.items.all())
        if not lines:
            return 'empty'
        active = [line for line in lines if line.status != Sale.STATUS_CANCELLED]
        if not active:
            return Sale.STATUS_CANCELLED
        if all(line.status in (Sale.STATUS_PREPARED, Sale.STATUS_COMPLETED) for line in active):
            return 'ready'
        if any(line.status == Sale.STATUS_PREPARING for line in active):
            return Sale.STATUS_PREPARING
        return Sale.STATUS_CREATED

    @property
    def pending_items(self):
        return self.items.filter(status__in=Sale.PRE_CONSUMPTION_STATUSES)


class Sale(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile Payment'),
        ('transfer', 'Bank Transfer'),
    )

    STATUS_CREATED = 'created'
    STATUS_ACCEPTED = 'accepted'
    STATUS_PREPARING = 'preparing'
    STATUS_PREPARED = 'prepared'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_CREATED, 'Order Created'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_PREPARING, 'Preparing'),
        (STATUS_PREPARED, 'Prepared / Served'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )
    # Statuses reached before ingredients have actually been consumed.
    PRE_CONSUMPTION_STATUSES = {STATUS_CREATED, STATUS_ACCEPTED, STATUS_PREPARING}
    
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, null=True, blank=True, related_name='items',
        help_text='The customer ticket this line belongs to. Null for standalone/legacy single-product sales.',
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
    actual_cogs = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Actual cost of goods sold at the time of this sale. Captured once and never recalculated, so later inventory price changes cannot alter historical cost.',
    )
    cogs_breakdown = models.JSONField(
        null=True, blank=True,
        help_text='Which inventory batches/quantities/costs made up actual_cogs, for auditability.',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_prepared',
        help_text='Staff member who marked this dish as prepared/served, triggering inventory consumption.',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_cancelled',
    )
    cancellation_reason = models.TextField(blank=True)

    def clean(self):
        if self.stay_id and self.stay and self.stay.is_closed:
            raise ValidationError({'stay': 'Sales cannot be recorded for a guest who has already checked out or whose stay is closed.'})
    
    def save(self, *args, **kwargs):
        if self.order_id:
            # Shared ticket details live on the Order; keep the line in sync
            # so existing per-Sale reporting and invoicing keep working.
            self.customer = self.order.customer
            self.room = self.order.room
            self.stay = self.order.stay
            self.payment_method = self.order.payment_method
        if self.stay_id:
            self.customer = self.stay.customer
            self.room = self.stay.room
        if self.product:
            self.unit_price = self.product.selling_price
            self.total_amount = self.quantity * self.unit_price
        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


@receiver(post_save, sender=Sale)
def reduce_product_stock(sender, instance, created, **kwargs):
    if not created:
        return
    product = instance.product

    if product.costing_method == product.COSTING_METHOD_MANUAL:
        # Manual-costed products are genuinely stocked retail items (bottled
        # drinks, snacks) - they leave the shelf the instant the sale is
        # made, so deduct now and consider the order complete immediately.
        product.quantity_in_stock -= instance.quantity
        product.save()
        Sale.objects.filter(pk=instance.pk).update(status=Sale.STATUS_COMPLETED)
    # Recipe-costed kitchen dishes do NOT consume inventory here. Creating an
    # order must not be treated as consuming ingredients - consumption only
    # happens when the dish is actually prepared/served, via
    # SaleWorkflowService.mark_prepared() in sales/services.py.


@receiver(pre_delete, sender=Sale)
def restore_product_stock(sender, instance, **kwargs):
    product = instance.product
    if product.costing_method == product.COSTING_METHOD_MANUAL:
        product.quantity_in_stock += instance.quantity
        product.save()
    # Recipe-costed dishes never decremented quantity_in_stock, so there is
    # nothing to restore there on delete. Note: raw ingredient batches
    # already consumed by a prepared order are NOT currently reversed when
    # a Sale is deleted - deleting a prepared/completed order does not put
    # ingredients back into inventory. Cancel *before* preparation instead.
