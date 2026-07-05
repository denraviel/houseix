from django.test import TestCase
from django.urls import reverse

from .models import CustomUser, JobPosition
from .services import NavigationService


class JobPositionAuthorizationTests(TestCase):
    def setUp(self):
        self.cleaner_position = JobPosition.objects.get(code='cleaner')
        self.cashier_position = JobPosition.objects.get(code='cashier')
        self.housekeeping_manager_position = JobPosition.objects.get(code='housekeeping_supervisor')
        self.cleaner = CustomUser.objects.create_user(
            email='cleaner@example.com',
            password='password123',
            full_name='Cleaner User',
            phone_number='08000000901',
            role='staff',
            position=self.cleaner_position,
        )
        self.manager = CustomUser.objects.create_user(
            email='housekeeping.manager@example.com',
            password='password123',
            full_name='Housekeeping Manager',
            phone_number='08000000902',
            role='manager',
            position=self.housekeeping_manager_position,
        )

    def test_seeded_job_positions_exist(self):
        self.assertTrue(JobPosition.objects.filter(code='hotel_administrator', is_active=True).exists())
        self.assertTrue(JobPosition.objects.filter(code='maintenance_technician', is_active=True).exists())
        self.assertTrue(JobPosition.objects.filter(code='driver', is_active=True).exists())

    def test_navigation_service_filters_modules_by_position(self):
        cleaner_modules = NavigationService.get_accessible_modules(self.cleaner)
        manager_modules = NavigationService.get_accessible_modules(self.manager)

        self.assertIn(NavigationService.MODULE_MY_TASKS, cleaner_modules)
        self.assertIn(NavigationService.MODULE_MAINTENANCE, cleaner_modules)
        self.assertNotIn(NavigationService.MODULE_EXPENSES, cleaner_modules)
        self.assertNotIn(NavigationService.MODULE_SALES, cleaner_modules)

        self.assertIn(NavigationService.MODULE_INSPECTIONS, manager_modules)
        self.assertIn(NavigationService.MODULE_TASKS, manager_modules)
        self.assertNotIn(NavigationService.MODULE_SALES, manager_modules)

    def test_navigation_service_unions_multiple_positions(self):
        self.cleaner.positions.add(self.cashier_position)

        modules = NavigationService.get_accessible_modules(self.cleaner)

        self.assertIn(NavigationService.MODULE_MY_TASKS, modules)
        self.assertIn(NavigationService.MODULE_MAINTENANCE, modules)
        self.assertIn(NavigationService.MODULE_INVOICES, modules)
        self.assertIn(NavigationService.MODULE_EXPENSES, modules)

    def test_position_module_middleware_blocks_hidden_module(self):
        self.client.force_login(self.cleaner)

        response = self.client.get(reverse('expense_dashboard'))

        self.assertEqual(response.status_code, 403)

    def test_owner_retains_full_module_access_without_position(self):
        owner = CustomUser.objects.create_user(
            email='owner.auth@example.com',
            password='password123',
            full_name='Owner Auth',
            phone_number='08000000903',
            role='owner',
        )

        modules = NavigationService.get_accessible_modules(owner)

        self.assertIn(NavigationService.MODULE_STAFF_MANAGEMENT, modules)
        self.assertIn(NavigationService.MODULE_REPORTS, modules)
        self.assertIn(NavigationService.MODULE_EXPENSES, modules)
