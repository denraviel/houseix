from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import Task
from .services import MaintenanceWorkflowService, TaskAssignmentService


@receiver(post_save, sender=Task)
def sync_maintenance_issue_from_task(sender, instance, **kwargs):
    if instance.task_type != 'maintenance':
        return
    MaintenanceWorkflowService.sync_issue_from_task(task=instance)


@receiver(m2m_changed, sender=Task.required_positions.through)
def validate_required_positions_assignment(sender, instance, action, pk_set, **kwargs):
    if action not in ['pre_add', 'pre_set'] or not instance.assigned_to_id:
        return
    required_positions = instance.required_positions.model.objects.filter(pk__in=pk_set)
    try:
        TaskAssignmentService.validate_assignment(
            assigned_to=instance.assigned_to,
            required_positions=required_positions,
        )
    except ValidationError as exc:
        raise ValidationError(exc)
