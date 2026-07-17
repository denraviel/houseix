from django.db import models

# Create your models here.
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from accounts.models import CustomUser, JobPosition
from rooms.models import Room

from .validators import validate_maintenance_photo


class TaskTrackedModel(models.Model):
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_created',
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Task(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY_FOR_REVIEW = 'ready_for_review'
    STATUS_COMPLETED = 'completed'
    STATUS_REOPENED = 'reopened'

    TASK_TYPE_CHOICES = [
        ('room_cleaning', 'Room Cleaning'),
        ('housekeeping_inspection', 'Housekeeping Inspection'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_READY_FOR_REVIEW, 'Ready for Review'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REOPENED, 'Reopened'),
    ]

    title = models.CharField(max_length=200)
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    description = models.TextField(blank=True)
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
    )
    assigned_to = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='assigned_tasks',
        limit_choices_to={'role__in': ['staff']}
    )
    required_positions = models.ManyToManyField(
        JobPosition,
        blank=True,
        related_name='required_tasks',
        limit_choices_to={'is_active': True},
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateField()
    date_assigned = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requires_inspection = models.BooleanField(default=False)
    previous_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_up_tasks',
    )
    completion_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='created_tasks'
    )

    class Meta:
        ordering = ['-due_date', '-priority']

    def __str__(self):
        return self.title

    def is_overdue(self):
        return self.due_date < timezone.now().date() and self.status != self.STATUS_COMPLETED

    @property
    def is_ready_for_review(self):
        return self.status == self.STATUS_READY_FOR_REVIEW

    @property
    def can_be_inspected(self):
        return self.requires_inspection and self.status == self.STATUS_READY_FOR_REVIEW

    def _ordered_required_positions(self):
        cached_positions = getattr(self, '_prefetched_objects_cache', {}).get('required_positions')
        if cached_positions is not None:
            return sorted(
                [position for position in cached_positions if position.is_active],
                key=lambda position: (position.department, position.name),
            )
        return list(self.required_positions.filter(is_active=True).order_by('department', 'name'))

    @property
    def required_position(self):
        positions = self._ordered_required_positions()
        return positions[0] if positions else None

    @property
    def required_position_names(self):
        return [position.name for position in self._ordered_required_positions()]

    def clean(self):
        if self.assigned_to_id and self.pk:
            required_positions = self.required_positions.filter(is_active=True)
            if required_positions.exists() and not self.assigned_to.positions.filter(pk__in=required_positions.values_list('pk', flat=True)).exists():
                raise ValidationError(
                    {'assigned_to': 'Assigned user must have at least one of the required job positions.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RoomInspectionChecklist(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='inspections')
    bed_properly_made = models.BooleanField(default=False)
    bathroom_cleaned = models.BooleanField(default=False)
    floor_cleaned = models.BooleanField(default=False)
    towels_replaced = models.BooleanField(default=False)
    trash_removed = models.BooleanField(default=False)
    room_properly_arranged = models.BooleanField(default=False)
    inspector = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    inspection_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['task'], name='unique_room_inspection_per_task'),
        ]

    def __str__(self):
        return f"Inspection for {self.task.title} by {self.inspector}"

    def get_pass_count(self):
        return sum([
            self.bed_properly_made,
            self.bathroom_cleaned,
            self.floor_cleaned,
            self.towels_replaced,
            self.trash_removed,
            self.room_properly_arranged,
        ])


class PerformanceRating(models.Model):
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]
    staff = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='performance_ratings')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='ratings')
    task_type = models.CharField(max_length=50)
    task_description = models.TextField(blank=True)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    rated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='given_ratings')
    date_rated = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_rated']
        constraints = [
            models.UniqueConstraint(fields=['task'], name='unique_performance_rating_per_task'),
        ]

    def __str__(self):
        return f"Rating for {self.staff}: {self.rating}"


class InspectionTemplate(models.Model):
    ROLE_CLEANER = 'Cleaner'

    name = models.CharField(max_length=200, unique=True)
    role = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    applicable_positions = models.ManyToManyField(
        JobPosition,
        blank=True,
        related_name='inspection_templates',
        limit_choices_to={'is_active': True},
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_templates_created',
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_templates_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role', 'name']

    def __str__(self):
        return f"{self.name} ({self.role})"


class InspectionTemplateItem(models.Model):
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_STANDARD = 'standard'
    SEVERITY_DETAIL = 'detail'

    SECTION_BED_LIVING = 'bed_living'
    SECTION_BATHROOM = 'bathroom'
    SECTION_TOUCHPOINTS = 'touchpoints'
    SECTION_FLOORS_WASTE = 'floors_waste'
    SECTION_AMENITIES = 'amenities'

    SECTION_CHOICES = [
        (SECTION_BED_LIVING, 'Bed & Living'),
        (SECTION_BATHROOM, 'Bathroom'),
        (SECTION_TOUCHPOINTS, 'Touchpoints'),
        (SECTION_FLOORS_WASTE, 'Floors & Waste'),
        (SECTION_AMENITIES, 'Amenities'),
    ]
    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, 'Critical'),
        (SEVERITY_STANDARD, 'Standard'),
        (SEVERITY_DETAIL, 'Detail'),
    ]

    template = models.ForeignKey(InspectionTemplate, on_delete=models.CASCADE, related_name='items')
    section = models.CharField(max_length=50, choices=SECTION_CHOICES)
    description = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    deduction_points = models.PositiveIntegerField()
    display_order = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_template_items_created',
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspection_template_items_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']
        unique_together = ('template', 'description')

    def __str__(self):
        return f"{self.template.name} - {self.description}"


class TaskInspection(models.Model):
    RESULT_EXCELLENT = 'excellent'
    RESULT_PASS = 'pass'
    RESULT_FAIL = 'fail'

    RESULT_CHOICES = [
        (RESULT_EXCELLENT, 'Excellent'),
        (RESULT_PASS, 'Pass'),
        (RESULT_FAIL, 'Fail'),
    ]

    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name='inspection')
    template = models.ForeignKey(InspectionTemplate, on_delete=models.PROTECT, related_name='inspections')
    worker = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='task_inspections_as_worker',
        limit_choices_to={'role': 'staff'},
    )
    inspector = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='task_inspections_as_inspector',
    )
    starting_score = models.PositiveIntegerField(default=100)
    total_deductions = models.PositiveIntegerField(default=0)
    final_score = models.PositiveIntegerField(default=100)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, blank=True)
    inspector_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_inspections_created',
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_inspections_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Inspection for {self.task.title}"

    @property
    def is_submitted(self):
        return self.submitted_at is not None


class InspectionResult(models.Model):
    inspection = models.ForeignKey(TaskInspection, on_delete=models.CASCADE, related_name='results')
    template_item = models.ForeignKey(InspectionTemplateItem, on_delete=models.PROTECT, related_name='inspection_results')
    passed = models.BooleanField(null=True, blank=True)
    deduction_applied = models.PositiveIntegerField(default=0)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['template_item__display_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['inspection', 'template_item'], name='unique_result_per_template_item'),
        ]

    def __str__(self):
        return f"{self.inspection} - {self.template_item.description}"


class MaintenanceCategory(TaskTrackedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    assignable_positions = models.ManyToManyField(
        JobPosition,
        blank=True,
        related_name='maintenance_categories',
        limit_choices_to={'is_active': True},
    )

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Maintenance categories'

    def __str__(self):
        return self.name


class MaintenanceIssue(TaskTrackedModel):
    PRIORITY_EMERGENCY = 'emergency'
    PRIORITY_HIGH = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW = 'low'

    STATUS_REPORTED = 'reported'
    STATUS_ACKNOWLEDGED = 'acknowledged'
    STATUS_ASSIGNED = 'assigned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_WAITING_PARTS = 'waiting_parts'
    STATUS_WAITING_VENDOR = 'waiting_vendor'
    STATUS_COMPLETED = 'completed'
    STATUS_VERIFIED = 'verified'
    STATUS_REOPENED = 'reopened'

    PRIORITY_CHOICES = [
        (PRIORITY_EMERGENCY, 'Emergency'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_LOW, 'Low'),
    ]
    STATUS_CHOICES = [
        (STATUS_REPORTED, 'Reported'),
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_WAITING_PARTS, 'Waiting Parts'),
        (STATUS_WAITING_VENDOR, 'Waiting Vendor'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_REOPENED, 'Reopened'),
    ]

    issue_number = models.CharField(max_length=20, unique=True, blank=True, editable=False, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        MaintenanceCategory,
        on_delete=models.PROTECT,
        related_name='issues',
    )
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REPORTED)
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_issues',
    )
    reported_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='reported_maintenance_issues',
    )
    assigned_to = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_maintenance_issues',
        limit_choices_to={'role': 'staff'},
    )
    requires_external_vendor = models.BooleanField(default=False)
    requires_expense = models.BooleanField(default=False)
    task = models.OneToOneField(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_issue',
    )
    expense = models.ForeignKey(
        'expenses.Expense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_issues',
    )
    verified_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_maintenance_issues',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.issue_number or self.title

    def get_absolute_url(self):
        return reverse('maintenance_issue_detail', kwargs={'pk': self.pk})

    @property
    def status_badge_class(self):
        return {
            self.STATUS_REPORTED: 'secondary',
            self.STATUS_ACKNOWLEDGED: 'info',
            self.STATUS_ASSIGNED: 'primary',
            self.STATUS_IN_PROGRESS: 'primary',
            self.STATUS_WAITING_PARTS: 'warning text-dark',
            self.STATUS_WAITING_VENDOR: 'warning text-dark',
            self.STATUS_COMPLETED: 'success',
            self.STATUS_VERIFIED: 'success',
            self.STATUS_REOPENED: 'danger',
        }.get(self.status, 'secondary')

    @property
    def priority_badge_class(self):
        return {
            self.PRIORITY_EMERGENCY: 'danger',
            self.PRIORITY_HIGH: 'warning text-dark',
            self.PRIORITY_MEDIUM: 'info',
            self.PRIORITY_LOW: 'secondary',
        }.get(self.priority, 'secondary')

    @property
    def is_open(self):
        return self.status not in [self.STATUS_VERIFIED]

    def clean(self):
        if self.status == self.STATUS_VERIFIED:
            if not self.verified_by_id or not self.verified_at:
                raise ValidationError('Verified issues must record who verified the repair and when.')
        elif self.verified_by_id or self.verified_at:
            raise ValidationError('Verification details can only be set when the issue is verified.')
        if self.expense_id:
            self.requires_expense = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MaintenancePhoto(models.Model):
    issue = models.ForeignKey(MaintenanceIssue, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(
        upload_to='maintenance/issues/%Y/%m/',
        validators=[validate_maintenance_photo],
    )
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_photos_uploaded',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at', 'id']

    def __str__(self):
        return f'Photo for {self.issue}'


class MaintenanceActivity(models.Model):
    ACTIVITY_ISSUE_REPORTED = 'Issue Reported'
    ACTIVITY_ASSIGNED = 'Assigned'
    ACTIVITY_ESCALATED = 'Escalated'
    ACTIVITY_ENGINEER_VISITED = 'Engineer Visited'
    ACTIVITY_WAITING_PARTS = 'Waiting Parts'
    ACTIVITY_WAITING_VENDOR = 'Waiting Vendor'
    ACTIVITY_REPAIR_STARTED = 'Repair Started'
    ACTIVITY_REPAIR_COMPLETED = 'Repair Completed'
    ACTIVITY_VERIFIED = 'Verified'
    ACTIVITY_REJECTED = 'Rejected'
    ACTIVITY_REOPENED = 'Reopened'
    ACTIVITY_UPDATED = 'Updated'
    ACTIVITY_PRIORITY_CHANGED = 'Priority Changed'
    ACTIVITY_STATUS_CHANGED = 'Status Changed'
    ACTIVITY_PHOTO_UPLOADED = 'Photo Uploaded'
    ACTIVITY_EXPENSE_LINKED = 'Expense Linked'
    ACTIVITY_TASK_CREATED = 'Task Created'
    ACTIVITY_TASK_LINKED = 'Task Linked'

    issue = models.ForeignKey(MaintenanceIssue, on_delete=models.CASCADE, related_name='activities')
    activity = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_activities_performed',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Maintenance activities'

    def __str__(self):
        return f'{self.activity} - {self.issue}'