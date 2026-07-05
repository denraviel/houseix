from django.db import models
from django.conf import settings


class Customer(models.Model):
    customer_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        db_index=True,
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers_created',
    )
    created_by_full_name = models.CharField(max_length=255, blank=True)
    created_by_username = models.CharField(max_length=255, blank=True)
    created_by_role = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.customer_id or self.pk})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.customer_id:
            customer_id = f"CUST{self.pk:06d}"
            type(self).objects.filter(pk=self.pk, customer_id__isnull=True).update(customer_id=customer_id)
            self.customer_id = customer_id
