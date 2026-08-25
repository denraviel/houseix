from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from accounts.models import AuditLog, CustomUser, JobPosition

from .models import (
    InspectionResult,
    InspectionTemplate,
    MaintenanceActivity,
    MaintenanceIssue,
    MaintenancePhoto,
    Task,
    TaskInspection,
)
from .selectors import (
    average_resolution_time,
    maintenance_cost_by_category,
    maintenance_cost_by_room,
    maintenance_cost_by_vendor,
    maintenance_dashboard_snapshot,
    maintenance_issue_summary_by_category,
    maintenance_issue_summary_by_priority,
    maintenance_report_queryset,
)


class InspectionTemplateService:
    @staticmethod
    def active_templates(role=None):
        queryset = InspectionTemplate.objects.filter(is_active=True).order_by('role', 'name')
        if role:
            queryset = queryset.filter(role__iexact=role)
        return queryset

    @staticmethod
    def get_role_templates(role):
        return InspectionTemplateService.active_templates(role=role)

    @staticmethod
    def clone_template_items(inspection):
        existing_ids = set(inspection.results.values_list('template_item_id', flat=True))
        results = []
        for item in inspection.template.items.order_by('display_order', 'id'):
            if item.id in existing_ids:
                continue
            results.append(
                InspectionResult(
                    inspection=inspection,
                    template_item=item,
                )
            )
        if results:
            InspectionResult.objects.bulk_create(results)
        return inspection.results.select_related('template_item').order_by('template_item__display_order', 'id')


class TaskAssignmentService:
    ROLE_HIERARCHY = CustomUser.ROLE_HIERARCHY

    @classmethod
    def managed_position_ids(cls, actor):
        """
        Positions `actor` is authorized to assign tasks to, via the
        JobPosition.manages_positions authority graph. The result is the
        transitive closure: if Operations Manager manages Bar Supervisor,
        and Bar Supervisor manages Barman, Operations Manager also reaches
        Barman automatically. Authority never flows backwards along an edge,
        so Barman gains no authority over Bar Supervisor or Operations Manager.
        """
        actor_position_ids = set(
            actor.positions.filter(is_active=True).values_list('pk', flat=True)
        )
        if not actor_position_ids:
            return set()

        reachable = set()
        frontier = set(actor_position_ids)
        seen = set(actor_position_ids)
        # Bounded traversal guards against accidental cycles in admin-configured data.
        for _ in range(25):
            if not frontier:
                break
            next_ids = set(
                JobPosition.objects.filter(pk__in=frontier)
                .values_list('manages_positions__pk', flat=True)
            )
            next_ids.discard(None)
            next_ids -= seen
            if not next_ids:
                break
            reachable |= next_ids
            seen |= next_ids
            frontier = next_ids
        return reachable

    @classmethod
    def has_position_authority(cls, *, actor, assigned_to):
        managed_position_ids = cls.managed_position_ids(actor)
        if not managed_position_ids:
            return False
        return assigned_to.positions.filter(pk__in=managed_position_ids, is_active=True).exists()

    @classmethod
    def can_assign_to(cls, *, actor, assigned_to):
        if actor is None or assigned_to is None:
            return False
        if not getattr(actor, 'is_authenticated', False) or not actor.is_active or not assigned_to.is_active:
            return False
        if actor.pk == assigned_to.pk:
            return False
        if actor.role in {'owner', 'admin'}:
            return True
        if actor.role != 'manager':
            return False
        if assigned_to.is_descendant_of(actor):
            return True
        return cls.has_position_authority(actor=actor, assigned_to=assigned_to)

    @classmethod
    def assignment_candidates(cls, *, actor=None, required_positions=None):
        base_roles = ['admin', 'manager', 'staff'] if actor is not None else ['staff']
        queryset = CustomUser.objects.filter(
            is_active=True,
            role__in=base_roles,
        ).exclude(pk=getattr(actor, 'pk', None)).prefetch_related('positions').order_by('full_name')

        if actor is not None:
            if actor.role in {'owner', 'admin'}:
                pass
            elif actor.role == 'manager':
                managed_position_ids = cls.managed_position_ids(actor)
                descendant_ids = [
                    user.pk for user in queryset
                    if user.is_descendant_of(actor)
                ]
                queryset = queryset.filter(
                    models.Q(pk__in=descendant_ids) | models.Q(positions__pk__in=managed_position_ids)
                ).distinct()
            else:
                queryset = queryset.none()

        if required_positions is not None:
            required_position_ids = list(required_positions.values_list('pk', flat=True))
            if required_position_ids:
                queryset = queryset.filter(positions__in=required_position_ids).distinct()
        return queryset

    @classmethod
    def validate_assignment(cls, *, actor=None, assigned_to, required_positions):
        if assigned_to is None:
            return
        if actor is None:
            if assigned_to.role != 'staff':
                raise ValidationError(
                    f'{assigned_to.full_name} cannot be assigned without an assigning user context.'
                )
        elif not cls.can_assign_to(actor=actor, assigned_to=assigned_to):
            raise ValidationError(
                f'{actor.full_name} is not authorized to assign tasks to {assigned_to.full_name}. '
                'Tasks can only be assigned within your organizational jurisdiction.'
            )
        if required_positions is None:
            return
        required_position_ids = list(required_positions.values_list('pk', flat=True))
        if required_position_ids and not assigned_to.positions.filter(pk__in=required_position_ids).exists():
            raise ValidationError(
                f'{assigned_to.full_name} does not have any of the required job positions for this assignment.'
            )


class InspectionCalculationService:
    RESULT_EXCELLENT = TaskInspection.RESULT_EXCELLENT
    RESULT_PASS = TaskInspection.RESULT_PASS
    RESULT_FAIL = TaskInspection.RESULT_FAIL

    def __init__(self, inspection):
        self.inspection = inspection

    def results_queryset(self):
        return self.inspection.results.select_related('template_item').order_by('template_item__display_order', 'id')

    def validate_inspection(self):
        if self.inspection.locked:
            raise ValidationError('Locked inspections cannot be edited.')
        if not self.inspection.task.requires_inspection:
            raise ValidationError('This task is not configured for inspection.')
        unanswered = self.results_queryset().filter(passed__isnull=True).count()
        if unanswered:
            raise ValidationError('Every checklist item must be marked as pass or fail before submission.')

    def total_deductions(self):
        return sum(
            result.template_item.deduction_points
            for result in self.results_queryset()
            if result.passed is False
        )

    def final_score(self):
        return max(self.inspection.starting_score - self.total_deductions(), 0)

    def determine_result(self):
        score = self.final_score()
        if score >= 95:
            return self.RESULT_EXCELLENT
        if score >= 85:
            return self.RESULT_PASS
        return self.RESULT_FAIL

    @transaction.atomic
    def apply_scores(self):
        total_deductions = 0
        results_to_update = []
        for result in self.results_queryset():
            deduction = result.template_item.deduction_points if result.passed is False else 0
            if result.deduction_applied != deduction:
                result.deduction_applied = deduction
                results_to_update.append(result)
            total_deductions += deduction
        if results_to_update:
            InspectionResult.objects.bulk_update(results_to_update, ['deduction_applied'])
        final_score = max(self.inspection.starting_score - total_deductions, 0)
        result_value = self.determine_result()
        self.inspection.total_deductions = total_deductions
        self.inspection.final_score = final_score
        self.inspection.result = result_value
        return self.inspection


class InspectionWorkflowService:
    FOLLOW_UP_REASON = 'Re-clean required after failed inspection.'

    @staticmethod
    def _ensure_management_user(user):
        if getattr(user, 'role', None) not in ['owner', 'admin', 'manager']:
            raise ValidationError('Only owners, admins, and managers can inspect tasks.')

    @staticmethod
    def _log(actor, action_type, description):
        try:
            AuditLog.log(actor, action_type, description)
        except Exception:
            # Keep inspection workflow resilient if audit choices lag behind code.
            pass

    @classmethod
    @transaction.atomic
    def create_inspection(cls, *, task, template, inspector, notes=''):
        cls._ensure_management_user(inspector)
        if hasattr(task, 'inspection'):
            raise ValidationError('This task already has an inspection.')
        if not task.requires_inspection:
            raise ValidationError('This task is not configured for inspection.')
        if task.status != Task.STATUS_READY_FOR_REVIEW:
            raise ValidationError('Only tasks marked Ready for Review can be audited.')
        if not template.is_active:
            raise ValidationError('Only active inspection templates can be used.')
        if template.applicable_positions.exists():
            worker_position_ids = task.assigned_to.positions.values_list('pk', flat=True)
            if not template.applicable_positions.filter(pk__in=worker_position_ids).exists():
                raise ValidationError('This inspection template does not apply to the assigned worker positions.')

        inspection = TaskInspection.objects.create(
            task=task,
            template=template,
            worker=task.assigned_to,
            inspector=inspector,
            inspector_notes=notes or '',
            created_by=inspector,
            updated_by=inspector,
        )
        InspectionTemplateService.clone_template_items(inspection)
        cls._log(inspector, 'inspection_created', f'Created inspection for task {task.title}.')
        return inspection

    @classmethod
    @transaction.atomic
    def save_draft(cls, *, inspection, inspector_notes, results_data, user):
        cls._ensure_management_user(user)
        if inspection.locked:
            raise ValidationError('Locked inspections cannot be edited.')
        for result, payload in results_data.items():
            result.passed = payload['passed']
            result.comment = payload.get('comment', '') or ''
            result.save(update_fields=['passed', 'comment'])
        inspection.inspector = user
        inspection.inspector_notes = inspector_notes or ''
        inspection.updated_by = user
        inspection.save(update_fields=['inspector', 'inspector_notes', 'updated_by', 'updated_at'])
        cls._log(user, 'inspection_updated', f'Updated inspection draft for task {inspection.task.title}.')
        return inspection

    @classmethod
    @transaction.atomic
    def submit_inspection(cls, *, inspection, inspector_notes, results_data, user):
        cls.save_draft(
            inspection=inspection,
            inspector_notes=inspector_notes,
            results_data=results_data,
            user=user,
        )
        calculator = InspectionCalculationService(inspection)
        calculator.validate_inspection()
        calculator.apply_scores()
        inspection.submitted_at = timezone.now()
        inspection.locked = True
        inspection.updated_by = user
        inspection.save(
            update_fields=[
                'total_deductions',
                'final_score',
                'result',
                'submitted_at',
                'locked',
                'updated_by',
                'updated_at',
            ]
        )
        cls._log(user, 'inspection_submitted', f'Submitted inspection for task {inspection.task.title}.')
        cls._log(user, 'inspection_locked', f'Locked inspection for task {inspection.task.title}.')
        if inspection.result == TaskInspection.RESULT_FAIL:
            follow_up_task = cls.reopen_failed_task(inspection=inspection, user=user)
            return inspection, follow_up_task
        inspection.task.status = Task.STATUS_COMPLETED
        if inspection.task.completed_at is None:
            inspection.task.completed_at = timezone.now()
        inspection.task.save(update_fields=['status', 'completed_at', 'updated_at'])
        return inspection, None

    @classmethod
    @transaction.atomic
    def reopen_failed_task(cls, *, inspection, user):
        task = inspection.task
        task.status = Task.STATUS_REOPENED
        task.completion_notes = (
            (task.completion_notes + '\n\n') if task.completion_notes else ''
        ) + cls.FOLLOW_UP_REASON
        task.save(update_fields=['status', 'completion_notes', 'updated_at'])
        cls._log(user, 'task_reopened', f'Reopened task {task.title} after failed inspection.')

        follow_up_task = Task.objects.create(
            title=f'Follow-up: {task.title}',
            task_type=task.task_type,
            description='\n'.join(
                part
                for part in [
                    task.description.strip(),
                    cls.FOLLOW_UP_REASON,
                    f'Previous task ID: {task.pk}',
                ]
                if part
            ),
            assigned_to=task.assigned_to,
            priority='high',
            due_date=timezone.localdate(),
            status=Task.STATUS_PENDING,
            requires_inspection=task.requires_inspection,
            previous_task=task,
            created_by=user,
        )
        follow_up_task.required_positions.set(task.required_positions.all())
        cls._log(user, 'follow_up_task_created', f'Created follow-up task {follow_up_task.title}.')
        return follow_up_task


class MaintenanceNotificationService:
    @staticmethod
    def notify_admin(issue, message=''):
        return message or f'Maintenance issue {issue.issue_number} is awaiting admin attention.'

    @staticmethod
    def notify_assigned_user(issue, message=''):
        if issue.assigned_to_id:
            return message or f'Maintenance issue {issue.issue_number} has been assigned to {issue.assigned_to.full_name}.'
        return message or f'Maintenance issue {issue.issue_number} is currently unassigned.'

    @staticmethod
    def notify_manager(issue, message=''):
        return message or f'Maintenance issue {issue.issue_number} is ready for manager review.'


class MaintenanceIssueService:
    @staticmethod
    def _safe_audit(actor, action_type, description):
        try:
            AuditLog.log(actor, action_type, description)
        except Exception:
            pass

    @staticmethod
    def log_activity(*, issue, activity, user=None, notes=''):
        return MaintenanceActivity.objects.create(
            issue=issue,
            activity=activity,
            performed_by=user,
            notes=notes or '',
        )

    @staticmethod
    def generate_issue_number(issue):
        if issue.issue_number:
            return issue.issue_number
        issue_number = f'MTN{issue.pk:06d}'
        MaintenanceIssue.objects.filter(pk=issue.pk, issue_number='').update(issue_number=issue_number)
        issue.issue_number = issue_number
        return issue_number

    @classmethod
    def validate_issue(cls, issue):
        issue.full_clean()
        return issue

    @classmethod
    def _create_photos(cls, *, issue, uploaded_files, captions_text, user):
        uploaded_files = uploaded_files or []
        if not uploaded_files:
            return []
        captions = [line.strip() for line in (captions_text or '').splitlines()]
        photos = []
        for index, uploaded_file in enumerate(uploaded_files):
            photo = MaintenancePhoto.objects.create(
                issue=issue,
                image=uploaded_file,
                caption=captions[index] if index < len(captions) else '',
                uploaded_by=user,
            )
            photos.append(photo)
            cls.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_PHOTO_UPLOADED,
                user=user,
                notes=f'Uploaded photo {photo.image.name}.',
            )
        return photos

    @classmethod
    @transaction.atomic
    def create_issue(cls, *, cleaned_data, user, uploaded_files=None):
        issue = MaintenanceIssue(
            issue_number='',
            title=cleaned_data['title'],
            description=cleaned_data['description'],
            category=cleaned_data['category'],
            priority=cleaned_data['priority'],
            room=cleaned_data.get('room'),
            reported_by=user,
            requires_external_vendor=cleaned_data.get('requires_external_vendor', False),
            requires_expense=cleaned_data.get('requires_expense', False),
            status=MaintenanceIssue.STATUS_REPORTED,
            created_by=user,
            updated_by=user,
        )
        cls.validate_issue(issue)
        issue.save()
        cls.generate_issue_number(issue)
        cls.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_ISSUE_REPORTED,
            user=user,
            notes=f'Reported issue {issue.issue_number}.',
        )
        cls._safe_audit(user, 'task_updated', f'Reported maintenance issue {issue.issue_number}: {issue.title}')
        cls._create_photos(
            issue=issue,
            uploaded_files=uploaded_files,
            captions_text=cleaned_data.get('photo_captions', ''),
            user=user,
        )
        return issue

    @classmethod
    @transaction.atomic
    def update_issue(cls, *, issue, cleaned_data, user, uploaded_files=None):
        if issue.status == MaintenanceIssue.STATUS_VERIFIED:
            raise ValidationError('Verified maintenance issues cannot be edited.')
        previous_priority = issue.priority
        issue.title = cleaned_data['title']
        issue.description = cleaned_data['description']
        issue.category = cleaned_data['category']
        issue.priority = cleaned_data['priority']
        issue.room = cleaned_data.get('room')
        issue.requires_external_vendor = cleaned_data.get('requires_external_vendor', False)
        issue.requires_expense = cleaned_data.get('requires_expense', False) or bool(issue.expense_id)
        issue.updated_by = user
        cls.validate_issue(issue)
        issue.save()
        cls.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_UPDATED,
            user=user,
            notes=f'Updated maintenance issue {issue.issue_number}.',
        )
        if previous_priority != issue.priority:
            cls.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_PRIORITY_CHANGED,
                user=user,
                notes=f'Priority changed from {previous_priority} to {issue.priority}.',
            )
        cls._safe_audit(user, 'task_updated', f'Updated maintenance issue {issue.issue_number}.')
        cls._create_photos(
            issue=issue,
            uploaded_files=uploaded_files,
            captions_text=cleaned_data.get('photo_captions', ''),
            user=user,
        )
        return issue


class MaintenanceWorkflowService:
    VERIFY_APPROVED = 'verified'
    VERIFY_REJECTED = 'rejected'

    ALLOWED_TRANSITIONS = {
        MaintenanceIssue.STATUS_REPORTED: {
            MaintenanceIssue.STATUS_ACKNOWLEDGED,
            MaintenanceIssue.STATUS_ASSIGNED,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_ACKNOWLEDGED: {
            MaintenanceIssue.STATUS_ASSIGNED,
            MaintenanceIssue.STATUS_IN_PROGRESS,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_ASSIGNED: {
            MaintenanceIssue.STATUS_IN_PROGRESS,
            MaintenanceIssue.STATUS_WAITING_PARTS,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_COMPLETED,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_IN_PROGRESS: {
            MaintenanceIssue.STATUS_WAITING_PARTS,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_COMPLETED,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_WAITING_PARTS: {
            MaintenanceIssue.STATUS_IN_PROGRESS,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_COMPLETED,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_WAITING_VENDOR: {
            MaintenanceIssue.STATUS_ACKNOWLEDGED,
            MaintenanceIssue.STATUS_ASSIGNED,
            MaintenanceIssue.STATUS_IN_PROGRESS,
            MaintenanceIssue.STATUS_COMPLETED,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_COMPLETED: {
            MaintenanceIssue.STATUS_VERIFIED,
            MaintenanceIssue.STATUS_REOPENED,
        },
        MaintenanceIssue.STATUS_REOPENED: {
            MaintenanceIssue.STATUS_ACKNOWLEDGED,
            MaintenanceIssue.STATUS_ASSIGNED,
            MaintenanceIssue.STATUS_IN_PROGRESS,
            MaintenanceIssue.STATUS_WAITING_PARTS,
            MaintenanceIssue.STATUS_WAITING_VENDOR,
            MaintenanceIssue.STATUS_COMPLETED,
        },
        MaintenanceIssue.STATUS_VERIFIED: set(),
    }

    @classmethod
    def _log_status_change(cls, *, issue, previous_status, user, notes=''):
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_STATUS_CHANGED,
            user=user,
            notes=notes or f'Status changed from {previous_status} to {issue.status}.',
        )

    @classmethod
    def _validate_transition(cls, *, issue, new_status):
        if new_status == issue.status:
            return
        allowed_statuses = cls.ALLOWED_TRANSITIONS.get(issue.status, set())
        if new_status not in allowed_statuses:
            raise ValidationError(
                f'Cannot move maintenance issue from {issue.get_status_display()} to '
                f'{dict(MaintenanceIssue.STATUS_CHOICES).get(new_status, new_status)}.'
            )

    @staticmethod
    def _task_priority(issue_priority):
        if issue_priority in [MaintenanceIssue.PRIORITY_EMERGENCY, MaintenanceIssue.PRIORITY_HIGH]:
            return 'high'
        if issue_priority == MaintenanceIssue.PRIORITY_LOW:
            return 'low'
        return 'medium'

    @classmethod
    def create_task_for_issue(cls, *, issue, assigned_to, due_date, user, title='', description=''):
        if assigned_to is None:
            raise ValidationError('A staff user must be assigned before creating a maintenance task.')
        task = Task.objects.create(
            title=title or f'Repair: {issue.title}',
            task_type='maintenance',
            description=description or issue.description,
            room=issue.room,
            assigned_to=assigned_to,
            priority=cls._task_priority(issue.priority),
            due_date=due_date,
            status=Task.STATUS_PENDING,
            requires_inspection=False,
            created_by=user,
        )
        category_positions = issue.category.assignable_positions.filter(is_active=True)
        if category_positions.exists():
            task.required_positions.set(category_positions)
            TaskAssignmentService.validate_assignment(actor=user, assigned_to=assigned_to, required_positions=category_positions)
        issue.task = task
        issue.updated_by = user
        issue.save(update_fields=['task', 'updated_by', 'updated_at'])
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_TASK_CREATED,
            user=user,
            notes=f'Created linked task {task.title}.',
        )
        return task

    @classmethod
    @transaction.atomic
    def assign_issue(cls, *, issue, cleaned_data, user):
        previous_assignee = issue.assigned_to
        previous_priority = issue.priority
        previous_status = issue.status
        previous_task = issue.task

        assigned_to = cleaned_data.get('assigned_to')
        existing_task = cleaned_data.get('existing_task')
        create_task = cleaned_data.get('create_task')
        task_due_date = cleaned_data.get('task_due_date')
        requested_status = cleaned_data.get('status') or issue.status

        if create_task and existing_task:
            raise ValidationError('Choose either an existing task or create a new task, not both.')
        if create_task and assigned_to is None:
            raise ValidationError('Assign a staff user before creating a maintenance task.')
        if create_task and not task_due_date:
            raise ValidationError('A due date is required when creating a linked task.')
        if existing_task and existing_task.task_type != 'maintenance':
            raise ValidationError('Only maintenance tasks can be linked to maintenance issues.')
        if assigned_to is None and existing_task and existing_task.assigned_to_id:
            assigned_to = existing_task.assigned_to
        category_positions = issue.category.assignable_positions.filter(is_active=True)
        TaskAssignmentService.validate_assignment(
            actor=user,
            assigned_to=assigned_to,
            required_positions=category_positions,
        )

        issue.assigned_to = assigned_to
        issue.priority = cleaned_data['priority']
        issue.requires_external_vendor = cleaned_data.get('requires_external_vendor', False)
        issue.requires_expense = cleaned_data.get('requires_expense', False) or bool(issue.expense_id)

        if requested_status == MaintenanceIssue.STATUS_ASSIGNED and assigned_to is None:
            raise ValidationError('Assigned status requires an assigned maintenance staff member.')
        if requested_status == MaintenanceIssue.STATUS_WAITING_VENDOR and not issue.requires_external_vendor:
            issue.requires_external_vendor = True

        cls._validate_transition(issue=issue, new_status=requested_status)
        issue.status = requested_status
        issue.updated_by = user
        issue.save()

        if create_task:
            task = cls.create_task_for_issue(
                issue=issue,
                assigned_to=assigned_to,
                due_date=task_due_date,
                user=user,
                title=cleaned_data.get('task_title', ''),
                description=cleaned_data.get('task_description', ''),
            )
        elif existing_task:
            TaskAssignmentService.validate_assignment(
                actor=user,
                assigned_to=existing_task.assigned_to,
                required_positions=category_positions,
            )
            issue.task = existing_task
            if issue.assigned_to_id is None and existing_task.assigned_to_id:
                issue.assigned_to = existing_task.assigned_to
            issue.updated_by = user
            issue.save(update_fields=['task', 'assigned_to', 'updated_by', 'updated_at'])
            task = existing_task
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_TASK_LINKED,
                user=user,
                notes=f'Linked existing task {task.title}.',
            )
        else:
            task = previous_task

        if previous_assignee != issue.assigned_to:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_ASSIGNED,
                user=user,
                notes=(
                    f'Assigned to {issue.assigned_to.full_name}.'
                    if issue.assigned_to_id
                    else 'Issue is currently unassigned.'
                ),
            )
        if previous_priority != issue.priority:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_PRIORITY_CHANGED,
                user=user,
                notes=f'Priority changed from {previous_priority} to {issue.priority}.',
            )
        if previous_status != issue.status:
            cls._log_status_change(issue=issue, previous_status=previous_status, user=user)
        if task and previous_task != task:
            MaintenanceIssueService._safe_audit(user, 'task_assigned', f'Linked task {task.title} to maintenance issue {issue.issue_number}.')
        return issue

    @classmethod
    @transaction.atomic
    def escalate_issue(cls, *, issue, user, notes='', target_priority=''):
        issue.updated_by = user
        if target_priority and target_priority != issue.priority:
            previous_priority = issue.priority
            issue.priority = target_priority
            issue.save(update_fields=['priority', 'updated_by', 'updated_at'])
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_PRIORITY_CHANGED,
                user=user,
                notes=f'Priority changed from {previous_priority} to {issue.priority} during escalation.',
            )
        else:
            issue.save(update_fields=['updated_by', 'updated_at'])
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_ESCALATED,
            user=user,
            notes=notes or MaintenanceNotificationService.notify_admin(issue),
        )
        return issue

    @classmethod
    @transaction.atomic
    def update_status(cls, *, issue, new_status, user, notes=''):
        previous_status = issue.status
        cls._validate_transition(issue=issue, new_status=new_status)
        issue.status = new_status
        issue.updated_by = user
        if new_status == MaintenanceIssue.STATUS_COMPLETED:
            issue.resolved_at = timezone.now()
        elif new_status == MaintenanceIssue.STATUS_REOPENED:
            issue.resolved_at = None
            issue.verified_by = None
            issue.verified_at = None
        issue.save()
        cls._log_status_change(issue=issue, previous_status=previous_status, user=user, notes=notes)
        if new_status == MaintenanceIssue.STATUS_WAITING_VENDOR:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_WAITING_VENDOR,
                user=user,
                notes=notes or 'Waiting for external vendor.',
            )
        elif new_status == MaintenanceIssue.STATUS_WAITING_PARTS:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_WAITING_PARTS,
                user=user,
                notes=notes or 'Waiting for parts.',
            )
        elif new_status == MaintenanceIssue.STATUS_IN_PROGRESS:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_REPAIR_STARTED,
                user=user,
                notes=notes or 'Repair started.',
            )
        elif new_status == MaintenanceIssue.STATUS_COMPLETED:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_REPAIR_COMPLETED,
                user=user,
                notes=notes or 'Repair completed.',
            )
        elif new_status == MaintenanceIssue.STATUS_REOPENED:
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_REOPENED,
                user=user,
                notes=notes or 'Issue reopened.',
            )
        return issue

    @classmethod
    @transaction.atomic
    def verify_issue(cls, *, issue, decision, user, notes=''):
        if issue.status != MaintenanceIssue.STATUS_COMPLETED:
            raise ValidationError('Only completed maintenance issues can be verified.')
        if decision == cls.VERIFY_APPROVED:
            issue.status = MaintenanceIssue.STATUS_VERIFIED
            issue.verified_by = user
            issue.verified_at = timezone.now()
            issue.updated_by = user
            if issue.resolved_at is None:
                issue.resolved_at = timezone.now()
            issue.save()
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_VERIFIED,
                user=user,
                notes=notes or 'Repair verified successfully.',
            )
            return issue
        if decision != cls.VERIFY_REJECTED:
            raise ValidationError('Unsupported verification decision.')
        return cls.reopen_issue(issue=issue, user=user, notes=notes or 'Repair verification failed.')

    @classmethod
    @transaction.atomic
    def reopen_issue(cls, *, issue, user, notes=''):
        previous_status = issue.status
        issue.status = MaintenanceIssue.STATUS_REOPENED
        issue.verified_by = None
        issue.verified_at = None
        issue.resolved_at = None
        issue.updated_by = user
        issue.save()
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_REJECTED,
            user=user,
            notes=notes or 'Repair rejected.',
        )
        cls._log_status_change(issue=issue, previous_status=previous_status, user=user, notes='Status changed to reopened.')
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_REOPENED,
            user=user,
            notes=notes or 'Issue reopened.',
        )
        if issue.task_id and issue.task.status == Task.STATUS_COMPLETED:
            issue.task.status = Task.STATUS_REOPENED
            issue.task.completed_at = None
            issue.task.save(update_fields=['status', 'completed_at', 'updated_at'])
        return issue

    @classmethod
    @transaction.atomic
    def link_expense(cls, *, issue, expense, user):
        issue.expense = expense
        issue.requires_expense = True
        issue.updated_by = user
        issue.save(update_fields=['expense', 'requires_expense', 'updated_by', 'updated_at'])
        MaintenanceIssueService.log_activity(
            issue=issue,
            activity=MaintenanceActivity.ACTIVITY_EXPENSE_LINKED,
            user=user,
            notes=f'Linked expense {expense.expense_number}.',
        )
        return issue

    @classmethod
    @transaction.atomic
    def sync_issue_from_task(cls, *, task):
        try:
            issue = task.maintenance_issue
        except MaintenanceIssue.DoesNotExist:
            return None
        updates = []
        if issue.assigned_to_id != task.assigned_to_id:
            issue.assigned_to = task.assigned_to
            updates.append('assigned_to')
        if task.status == Task.STATUS_COMPLETED and issue.status not in [MaintenanceIssue.STATUS_COMPLETED, MaintenanceIssue.STATUS_VERIFIED]:
            previous_status = issue.status
            issue.status = MaintenanceIssue.STATUS_COMPLETED
            issue.resolved_at = issue.resolved_at or timezone.now()
            updates.extend(['status', 'resolved_at'])
            issue.save(update_fields=updates + ['updated_at'])
            cls._log_status_change(issue=issue, previous_status=previous_status, user=task.assigned_to, notes='Completed from linked task.')
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_REPAIR_COMPLETED,
                user=task.assigned_to,
                notes='Linked maintenance task was completed.',
            )
            return issue
        if task.status == Task.STATUS_REOPENED and issue.status != MaintenanceIssue.STATUS_REOPENED:
            previous_status = issue.status
            issue.status = MaintenanceIssue.STATUS_REOPENED
            issue.resolved_at = None
            issue.verified_by = None
            issue.verified_at = None
            updates.extend(['status', 'resolved_at', 'verified_by', 'verified_at'])
            issue.save(update_fields=updates + ['updated_at'])
            cls._log_status_change(issue=issue, previous_status=previous_status, user=task.assigned_to, notes='Reopened from linked task.')
            MaintenanceIssueService.log_activity(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_REOPENED,
                user=task.assigned_to,
                notes='Linked maintenance task was reopened.',
            )
            return issue
        if updates:
            issue.save(update_fields=updates + ['updated_at'])
        return issue


class MaintenanceReportService:
    @staticmethod
    def dashboard_snapshot(user):
        return maintenance_dashboard_snapshot(user)

    @staticmethod
    def report_queryset():
        return maintenance_report_queryset()

    @staticmethod
    def issues_by_category(queryset=None):
        return maintenance_issue_summary_by_category(queryset=queryset)

    @staticmethod
    def issues_by_priority(queryset=None):
        return maintenance_issue_summary_by_priority(queryset=queryset)

    @staticmethod
    def average_resolution_time(queryset=None):
        return average_resolution_time(queryset=queryset)

    @staticmethod
    def maintenance_cost_by_category(queryset=None):
        return maintenance_cost_by_category(queryset=queryset)

    @staticmethod
    def maintenance_cost_by_room(queryset=None):
        return maintenance_cost_by_room(queryset=queryset)

    @staticmethod
    def maintenance_cost_by_vendor(queryset=None):
        return maintenance_cost_by_vendor(queryset=queryset)
