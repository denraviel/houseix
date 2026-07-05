from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.conf import settings

from customers.models import Customer
from rooms.models import Room


class GuestStay(models.Model):
    STATUS_RESERVED = 'reserved'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_CHECKED_OUT = 'checked_out'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_CHECKED_IN, 'Checked In'),
        (STATUS_CHECKED_OUT, 'Checked Out'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    ACTIVE_STATUSES = [STATUS_RESERVED, STATUS_CHECKED_IN]
    CLOSED_STATUSES = [STATUS_CHECKED_OUT, STATUS_CANCELLED]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='stays')
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='stays')
    check_in_date = models.DateField(default=timezone.now)
    check_out_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2)
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stays_created',
    )
    created_by_full_name = models.CharField(max_length=255, blank=True)
    created_by_username = models.CharField(max_length=255, blank=True)
    created_by_role = models.CharField(max_length=50, blank=True)
    checked_in_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stays_checked_in',
    )
    checked_in_by_full_name = models.CharField(max_length=255, blank=True)
    checked_in_by_username = models.CharField(max_length=255, blank=True)
    checked_in_by_role = models.CharField(max_length=50, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stays_checked_out',
    )
    checked_out_by_full_name = models.CharField(max_length=255, blank=True)
    checked_out_by_username = models.CharField(max_length=255, blank=True)
    checked_out_by_role = models.CharField(max_length=50, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.full_name} - {self.room.room_number} ({self.get_status_display()})"

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    def clean(self):
        if self.check_out_date and self.check_out_date < self.check_in_date:
            raise ValidationError({'check_out_date': 'Check-out date cannot be before check-in date.'})
        if self.pk:
            original = GuestStay.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if original in self.CLOSED_STATUSES and self.status in self.ACTIVE_STATUSES:
                raise ValidationError({'status': 'This stay is already closed. Create a new booking for a new check-in.'})
        if self.status in self.ACTIVE_STATUSES:
            if self.room_id:
                if self.pk:
                    active_exists = GuestStay.objects.filter(
                        room_id=self.room_id,
                        status__in=self.ACTIVE_STATUSES,
                    ).exclude(pk=self.pk).exists()
                else:
                    active_exists = GuestStay.objects.filter(
                        room_id=self.room_id,
                        status__in=self.ACTIVE_STATUSES,
                    ).exists()
                if active_exists:
                    raise ValidationError({'room': 'This room already has an active stay (Reserved/Checked In).'})

    def save(self, *args, **kwargs):
        if self.daily_rate is None and self.room_id:
            self.daily_rate = self.room.daily_rate
        self.full_clean()
        super().save(*args, **kwargs)
        self._sync_room_status()

    def _sync_room_status(self):
        room = self.room
        if self.status == self.STATUS_CHECKED_IN:
            target = Room.STATUS_OCCUPIED
        elif self.status == self.STATUS_RESERVED:
            target = Room.STATUS_RESERVED
        else:
            active = GuestStay.objects.filter(
                room_id=room.id,
                status__in=self.ACTIVE_STATUSES,
            ).exclude(pk=self.pk).exists()
            target = room.status if active else Room.STATUS_AVAILABLE
        if room.status != target:
            Room.objects.filter(pk=room.pk).update(status=target, updated_at=timezone.now())
