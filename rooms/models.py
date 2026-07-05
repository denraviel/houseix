from django.db import models


class Room(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_OCCUPIED = 'occupied'
    STATUS_RESERVED = 'reserved'
    STATUS_MAINTENANCE = 'maintenance'

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_OCCUPIED, 'Occupied'),
        (STATUS_RESERVED, 'Reserved'),
        (STATUS_MAINTENANCE, 'Maintenance'),
    ]

    TYPE_SINGLE = 'single'
    TYPE_LARGE_LUXURY = 'large_luxury'
    TYPE_TWO_BED_APT = 'two_bedroom_apartment'
    TYPE_PENTHOUSE = 'penthouse'

    ROOM_TYPE_CHOICES = [
        (TYPE_SINGLE, 'Single Room'),
        (TYPE_LARGE_LUXURY, 'Large Luxury Room'),
        (TYPE_TWO_BED_APT, 'Two Bedroom Apartment'),
        (TYPE_PENTHOUSE, 'Penthouse'),
    ]

    room_number = models.CharField(max_length=20, unique=True)
    room_type = models.CharField(max_length=40, choices=ROOM_TYPE_CHOICES)
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['room_number']

    def __str__(self):
        return f"Room {self.room_number}"
