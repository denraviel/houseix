from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        positions = extra_fields.pop('positions', None)
        legacy_position = extra_fields.pop('position', None)
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if positions is not None:
            user.positions.set(positions)
        elif legacy_position is not None:
            user.positions.set([legacy_position])
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class AccountTrackedModel(models.Model):
    created_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    updated_by = models.ForeignKey(
        'CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class JobPosition(AccountTrackedModel):
    DEPARTMENT_GENERAL_MANAGEMENT = 'general_management'
    DEPARTMENT_FRONT_OFFICE = 'front_office'
    DEPARTMENT_HOUSEKEEPING = 'housekeeping'
    DEPARTMENT_MAINTENANCE = 'maintenance'
    DEPARTMENT_SECURITY = 'security'
    DEPARTMENT_FOOD_BEVERAGE = 'food_beverage'
    DEPARTMENT_STORE = 'store'
    DEPARTMENT_FINANCE = 'finance'
    DEPARTMENT_SALES_MARKETING = 'sales_marketing'
    DEPARTMENT_DRIVER = 'driver'
    DEPARTMENT_GENERAL_STAFF = 'general_staff'

    DEPARTMENT_CHOICES = (
        (DEPARTMENT_GENERAL_MANAGEMENT, 'General Management'),
        (DEPARTMENT_FRONT_OFFICE, 'Front Office'),
        (DEPARTMENT_HOUSEKEEPING, 'Housekeeping'),
        (DEPARTMENT_MAINTENANCE, 'Maintenance'),
        (DEPARTMENT_SECURITY, 'Security'),
        (DEPARTMENT_FOOD_BEVERAGE, 'Food & Beverage'),
        (DEPARTMENT_STORE, 'Store'),
        (DEPARTMENT_FINANCE, 'Finance'),
        (DEPARTMENT_SALES_MARKETING, 'Sales & Marketing'),
        (DEPARTMENT_DRIVER, 'Driver'),
        (DEPARTMENT_GENERAL_STAFF, 'General Staff'),
    )

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['department', 'name']

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    )
    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    positions = models.ManyToManyField(
        JobPosition,
        blank=True,
        related_name='users',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def _ordered_positions(self):
        cached_positions = getattr(self, '_prefetched_objects_cache', {}).get('positions')
        if cached_positions is not None:
            return sorted(
                [position for position in cached_positions if position.is_active],
                key=lambda position: (position.department, position.name),
            )
        return list(self.positions.filter(is_active=True).order_by('department', 'name'))

    @property
    def position(self):
        positions = self._ordered_positions()
        return positions[0] if positions else None

    @property
    def position_names(self):
        return [position.name for position in self._ordered_positions()]

    @property
    def position_name(self):
        primary_position = self.position
        return primary_position.name if primary_position else ''


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('user_created', 'User Created'),
        ('user_edited', 'User Edited'),
        ('user_status_changed', 'User Status Changed'),
        ('product_created', 'Product Created'),
        ('product_updated', 'Product Updated'),
        ('product_deleted', 'Product Deleted'),
        ('product_toggled', 'Product Toggled'),
        ('inventory_created', 'Inventory Created'),
        ('inventory_updated', 'Inventory Updated'),
        ('inventory_deleted', 'Inventory Deleted'),
        ('inventory_stock_added', 'Inventory Stock Added'),
        ('task_assigned', 'Task Assigned'),
        ('task_updated', 'Task Updated'),
        ('task_deleted', 'Task Deleted'),
        ('staff_rated', 'Staff Rated'),
    )

    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} by {self.actor_id or 'system'}"

    @classmethod
    def log(cls, actor, action_type, description=''):
        return cls.objects.create(actor=actor, action_type=action_type, description=description or '')


class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ('customer_created', 'Customer Created'),
        ('customer_updated', 'Customer Updated'),
        ('booking_created', 'Booking Created'),
        ('booking_edited', 'Booking Edited'),
        ('guest_checked_in', 'Guest Checked In'),
        ('guest_checked_out', 'Guest Checked Out'),
    )

    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    user_full_name = models.CharField(max_length=255)
    user_username = models.CharField(max_length=255)
    user_role = models.CharField(max_length=20)
    customer = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    booking = models.ForeignKey('stays.GuestStay', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.action_type}"

    @classmethod
    def log(cls, user, action_type, customer=None, booking=None, notes=''):
        return cls.objects.create(
            action_type=action_type,
            user=user,
            user_full_name=(getattr(user, 'full_name', '') or ''),
            user_username=(getattr(user, 'email', '') or ''),
            user_role=(getattr(user, 'role', '') or ''),
            customer=customer,
            booking=booking,
            notes=notes or '',
        )
