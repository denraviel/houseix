from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import CustomUser, JobPosition, ModulePermission
from rooms.models import Room

from .forms import TaskForm
from .models import InspectionTemplate, MaintenanceActivity, MaintenanceCategory, MaintenanceIssue, Task, TaskInspection
from .services import InspectionWorkflowService, MaintenanceIssueService, MaintenanceWorkflowService, TaskAssignmentService


class InspectionWorkflowTests(TestCase):
    def setUp(self):
        self.cleaner_position = JobPosition.objects.get(code='cleaner')
        self.my_tasks_module = ModulePermission.objects.get(code='my_tasks')
        self.manager = CustomUser.objects.create_user(
            email='manager@example.com',
            password='password123',
            full_name='Manager User',
            phone_number='08000000001',
            role='manager',
        )
        self.staff = CustomUser.objects.create_user(
            email='staff@example.com',
            password='password123',
            full_name='Cleaner User',
            phone_number='08000000002',
            role='staff',
            position=self.cleaner_position,
            module_permissions=[self.my_tasks_module],
        )
        self.room = Room.objects.create(
            room_number='101',
            room_type=Room.TYPE_SINGLE,
            daily_rate='25000.00',
        )
        self.template = InspectionTemplate.objects.get(name='Cleaner Room Inspection')

    def create_task(self, **overrides):
        defaults = {
            'title': 'Clean Room 101',
            'task_type': 'room_cleaning',
            'description': 'Deep clean and reset guest room.',
            'room': self.room,
            'assigned_to': self.staff,
            'priority': 'medium',
            'due_date': timezone.localdate(),
            'status': Task.STATUS_READY_FOR_REVIEW,
            'requires_inspection': True,
            'created_by': self.manager,
        }
        defaults.update(overrides)
        task = Task.objects.create(**defaults)
        task.required_positions.set([self.cleaner_position])
        return task

    def test_seeded_cleaner_template_exists(self):
        self.assertEqual(self.template.role, 'Cleaner')
        self.assertEqual(self.template.items.count(), 27)
        self.assertTrue(self.template.applicable_positions.filter(pk=self.cleaner_position.pk).exists())

    def test_task_form_initializes_for_unsaved_task(self):
        form = TaskForm()

        self.assertIn('assigned_to', form.fields)
        self.assertEqual(form.fields['assigned_to'].queryset.count(), 1)

    def test_staff_completion_moves_task_to_ready_for_review(self):
        task = self.create_task(status=Task.STATUS_IN_PROGRESS)
        self.client.force_login(self.staff)

        response = self.client.post(reverse('staff_task_complete', args=[task.pk]))

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_READY_FOR_REVIEW)
        self.assertIsNotNone(task.completed_at)

    def test_submit_passed_inspection_completes_task(self):
        task = self.create_task()
        inspection = InspectionWorkflowService.create_inspection(
            task=task,
            template=self.template,
            inspector=self.manager,
            notes='Initial review started.',
        )
        results_data = {
            result: {'passed': True, 'comment': ''}
            for result in inspection.results.select_related('template_item')
        }

        submitted, follow_up = InspectionWorkflowService.submit_inspection(
            inspection=inspection,
            inspector_notes='Everything passed.',
            results_data=results_data,
            user=self.manager,
        )

        task.refresh_from_db()
        self.assertTrue(submitted.locked)
        self.assertEqual(submitted.result, TaskInspection.RESULT_EXCELLENT)
        self.assertEqual(submitted.final_score, 100)
        self.assertEqual(task.status, Task.STATUS_COMPLETED)
        self.assertIsNone(follow_up)

    def test_submit_failed_inspection_reopens_task_and_creates_follow_up(self):
        task = self.create_task()
        inspection = InspectionWorkflowService.create_inspection(
            task=task,
            template=self.template,
            inspector=self.manager,
            notes='Initial review started.',
        )
        results = list(inspection.results.select_related('template_item'))
        results_data = {}
        for index, result in enumerate(results):
            results_data[result] = {
                'passed': False if index < 3 else True,
                'comment': 'Issue found' if index < 3 else '',
            }

        submitted, follow_up = InspectionWorkflowService.submit_inspection(
            inspection=inspection,
            inspector_notes='Major cleaning gaps found.',
            results_data=results_data,
            user=self.manager,
        )

        task.refresh_from_db()
        self.assertTrue(submitted.locked)
        self.assertEqual(submitted.result, TaskInspection.RESULT_FAIL)
        self.assertEqual(task.status, Task.STATUS_REOPENED)
        self.assertIsNotNone(follow_up)
        self.assertEqual(follow_up.previous_task, task)
        self.assertEqual(follow_up.assigned_to, self.staff)
        self.assertTrue(follow_up.required_positions.filter(pk=self.cleaner_position.pk).exists())
        self.assertEqual(follow_up.priority, 'high')
        self.assertEqual(follow_up.status, Task.STATUS_PENDING)
        self.assertTrue(follow_up.requires_inspection)


class MaintenanceWorkflowTests(TestCase):
    def setUp(self):
        self.maintenance_position = JobPosition.objects.get(code='maintenance_technician')
        self.security_position = JobPosition.objects.get(code='security_officer')
        self.maintenance_module = ModulePermission.objects.get(code='maintenance')
        self.owner = CustomUser.objects.create_user(
            email='owner@example.com',
            password='password123',
            full_name='Owner User',
            phone_number='08000000011',
            role='owner',
        )
        self.admin = CustomUser.objects.create_user(
            email='admin@example.com',
            password='password123',
            full_name='Admin User',
            phone_number='08000000012',
            role='admin',
        )
        self.manager = CustomUser.objects.create_user(
            email='maintenance.manager@example.com',
            password='password123',
            full_name='Maintenance Manager',
            phone_number='08000000013',
            role='manager',
        )
        self.staff = CustomUser.objects.create_user(
            email='maintenance.staff@example.com',
            password='password123',
            full_name='Maintenance Staff',
            phone_number='08000000014',
            role='staff',
            position=self.maintenance_position,
            module_permissions=[self.maintenance_module],
        )
        self.room = Room.objects.create(
            room_number='203',
            room_type=Room.TYPE_LARGE_LUXURY,
            daily_rate='35000.00',
        )
        self.category = MaintenanceCategory.objects.get(name='Air Conditioning')

    def test_default_maintenance_categories_are_seeded(self):
        self.assertTrue(MaintenanceCategory.objects.filter(name='Electrical', is_active=True).exists())
        self.assertTrue(MaintenanceCategory.objects.filter(name='General', is_active=True).exists())
        self.assertTrue(self.category.assignable_positions.filter(pk=self.maintenance_position.pk).exists())

    def test_create_issue_generates_number_and_activity_log(self):
        issue = MaintenanceIssueService.create_issue(
            cleaned_data={
                'title': 'AC not cooling',
                'description': 'Room 203 air conditioner is blowing warm air.',
                'category': self.category,
                'priority': MaintenanceIssue.PRIORITY_HIGH,
                'room': self.room,
                'requires_external_vendor': False,
                'requires_expense': False,
                'photo_captions': '',
            },
            user=self.manager,
            uploaded_files=[],
        )

        self.assertTrue(issue.issue_number.startswith('MTN'))
        self.assertEqual(issue.reported_by, self.manager)
        self.assertEqual(issue.status, MaintenanceIssue.STATUS_REPORTED)
        self.assertTrue(
            MaintenanceActivity.objects.filter(
                issue=issue,
                activity=MaintenanceActivity.ACTIVITY_ISSUE_REPORTED,
            ).exists()
        )

    def test_staff_list_shows_only_assigned_issues(self):
        assigned_issue = MaintenanceIssueService.create_issue(
            cleaned_data={
                'title': 'Broken shower',
                'description': 'Shower head is damaged.',
                'category': MaintenanceCategory.objects.get(name='Bathroom'),
                'priority': MaintenanceIssue.PRIORITY_MEDIUM,
                'room': self.room,
                'requires_external_vendor': False,
                'requires_expense': False,
                'photo_captions': '',
            },
            user=self.manager,
            uploaded_files=[],
        )
        hidden_issue = MaintenanceIssueService.create_issue(
            cleaned_data={
                'title': 'Window broken',
                'description': 'Outer pane is cracked.',
                'category': MaintenanceCategory.objects.get(name='Windows'),
                'priority': MaintenanceIssue.PRIORITY_HIGH,
                'room': self.room,
                'requires_external_vendor': False,
                'requires_expense': False,
                'photo_captions': '',
            },
            user=self.manager,
            uploaded_files=[],
        )
        assigned_issue.assigned_to = self.staff
        assigned_issue.status = MaintenanceIssue.STATUS_ASSIGNED
        assigned_issue.updated_by = self.admin
        assigned_issue.save()
        hidden_issue.updated_by = self.admin
        hidden_issue.save()

        self.client.force_login(self.staff)
        response = self.client.get(reverse('maintenance_issue_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, assigned_issue.issue_number)
        self.assertNotContains(response, hidden_issue.issue_number)

    def test_owner_can_open_maintenance_issue_edit_page(self):
        issue = MaintenanceIssueService.create_issue(
            cleaned_data={
                'title': 'AC not cooling',
                'description': 'Room 203 air conditioner is blowing warm air.',
                'category': self.category,
                'priority': MaintenanceIssue.PRIORITY_HIGH,
                'room': self.room,
                'requires_external_vendor': False,
                'requires_expense': False,
                'photo_captions': '',
            },
            user=self.manager,
            uploaded_files=[],
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse('maintenance_issue_update', args=[issue.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, issue.title)

    def test_linked_task_completion_marks_issue_completed(self):
        issue = MaintenanceIssueService.create_issue(
            cleaned_data={
                'title': 'Generator leaking oil',
                'description': 'Leak observed during generator inspection.',
                'category': MaintenanceCategory.objects.get(name='Generator'),
                'priority': MaintenanceIssue.PRIORITY_EMERGENCY,
                'room': None,
                'requires_external_vendor': False,
                'requires_expense': True,
                'photo_captions': '',
            },
            user=self.manager,
            uploaded_files=[],
        )

        MaintenanceWorkflowService.assign_issue(
            issue=issue,
            cleaned_data={
                'assigned_to': self.staff,
                'existing_task': None,
                'create_task': True,
                'task_due_date': timezone.localdate(),
                'task_title': 'Repair generator oil leak',
                'task_description': 'Inspect seals and stop the leak.',
                'priority': MaintenanceIssue.PRIORITY_EMERGENCY,
                'status': MaintenanceIssue.STATUS_ASSIGNED,
                'requires_external_vendor': False,
                'requires_expense': True,
            },
            user=self.admin,
        )

        issue.refresh_from_db()
        self.assertIsNotNone(issue.task)
        self.assertEqual(issue.task.task_type, 'maintenance')
        self.assertTrue(issue.task.required_positions.filter(pk=self.maintenance_position.pk).exists())

        issue.task.status = Task.STATUS_COMPLETED
        issue.task.completed_at = timezone.now()
        issue.task.save(update_fields=['status', 'completed_at', 'updated_at'])

        issue.refresh_from_db()
        self.assertEqual(issue.status, MaintenanceIssue.STATUS_COMPLETED)
        self.assertIsNotNone(issue.resolved_at)

    def test_task_assignment_requires_matching_position(self):
        cleaner_position = JobPosition.objects.get(code='cleaner')
        cleaner = CustomUser.objects.create_user(
            email='cleaner.task@example.com',
            password='password123',
            full_name='Task Cleaner',
            phone_number='08000000015',
            role='staff',
            position=cleaner_position,
            module_permissions=[self.maintenance_module],
        )

        task = Task(
            title='Repair AC',
            task_type='maintenance',
            description='Repair the AC compressor.',
            room=self.room,
            assigned_to=cleaner,
            priority='high',
            due_date=timezone.localdate(),
            status=Task.STATUS_PENDING,
            requires_inspection=False,
            created_by=self.manager,
        )
        with self.assertRaises(ValidationError):
            task.save()
            task.required_positions.set([self.maintenance_position])

    def test_task_assignment_accepts_any_matching_position(self):
        multi_position_staff = CustomUser.objects.create_user(
            email='multi.position@example.com',
            password='password123',
            full_name='Multi Position Staff',
            phone_number='08000000016',
            role='staff',
            positions=[self.security_position, self.maintenance_position],
            module_permissions=[self.maintenance_module],
        )

        required_positions = JobPosition.objects.filter(pk__in=[self.maintenance_position.pk, self.security_position.pk])

        TaskAssignmentService.validate_assignment(
            assigned_to=multi_position_staff,
            required_positions=required_positions,
        )
class PositionAuthorityAssignmentTests(TestCase):
    """
    Covers task-assignment authority that is granted through the
    JobPosition.manages_positions graph rather than the reports_to chain.
    Mirrors the real hotel scenario: an Operations Manager and a Bar
    Supervisor can both hold role='manager', but only specific positions
    should be able to assign tasks to specific other positions.
    """

    def setUp(self):
        self.ops_manager_position = JobPosition.objects.get(code='operations_manager')
        self.bar_supervisor_position, _ = JobPosition.objects.get_or_create(
            code='bar_supervisor',
            defaults={
                'name': 'Bar Supervisor',
                'department': JobPosition.DEPARTMENT_FOOD_BEVERAGE,
            },
        )
        self.barman_position = JobPosition.objects.get(code='barman')

        # Direct edges: Ops Manager -> Bar Supervisor -> Barman.
        self.ops_manager_position.manages_positions.add(self.bar_supervisor_position)
        self.bar_supervisor_position.manages_positions.add(self.barman_position)

        self.ops_manager = CustomUser.objects.create_user(
            email='ops.manager@example.com',
            password='password123',
            full_name='Ops Manager',
            phone_number='08000000101',
            role='manager',
            positions=[self.ops_manager_position],
        )
        self.bar_supervisor = CustomUser.objects.create_user(
            email='bar.supervisor@example.com',
            password='password123',
            full_name='Bar Supervisor',
            phone_number='08000000102',
            role='manager',
            positions=[self.bar_supervisor_position],
        )
        self.barman = CustomUser.objects.create_user(
            email='barman@example.com',
            password='password123',
            full_name='Barman User',
            phone_number='08000000103',
            role='staff',
            positions=[self.barman_position],
        )

    def test_operations_manager_can_assign_to_barman_transitively(self):
        # No reports_to link exists between them; authority comes purely
        # from the position graph, and is transitive across Bar Supervisor.
        self.assertTrue(
            TaskAssignmentService.can_assign_to(actor=self.ops_manager, assigned_to=self.barman)
        )

    def test_bar_supervisor_can_assign_to_barman(self):
        self.assertTrue(
            TaskAssignmentService.can_assign_to(actor=self.bar_supervisor, assigned_to=self.barman)
        )

    def test_bar_supervisor_cannot_assign_to_operations_manager(self):
        # Same role ('manager'), no edge from Bar Supervisor to Operations
        # Manager in either direction other than the one we added -> must fail.
        self.assertFalse(
            TaskAssignmentService.can_assign_to(actor=self.bar_supervisor, assigned_to=self.ops_manager)
        )

    def test_barman_cannot_assign_to_bar_supervisor(self):
        self.assertFalse(
            TaskAssignmentService.can_assign_to(actor=self.barman, assigned_to=self.bar_supervisor)
        )

    def test_assignment_candidates_includes_positionally_managed_users(self):
        candidates = TaskAssignmentService.assignment_candidates(actor=self.bar_supervisor)
        self.assertIn(self.barman, list(candidates))
        self.assertNotIn(self.ops_manager, list(candidates))
