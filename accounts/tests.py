from django.test import TestCase
from django.contrib.auth import get_user_model
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


class AccountOnboardingTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner@example.com',
            password='Owner@12345',
            full_name='Owner User',
            phone_number='08000000111',
            username='owner.user',
            role='owner',
        )
        self.staff = self.UserModel.objects.create_user(
            email='staff@example.com',
            password='Staff@12345',
            full_name='Staff User',
            phone_number='08000000112',
            username='staff.user',
            role='staff',
            is_first_login=False,
        )

    def test_login_accepts_username(self):
        response = self.client.post(reverse('login'), {'username': 'staff.user', 'password': 'Staff@12345'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.staff.pk)

    def test_login_accepts_email(self):
        response = self.client.post(reverse('login'), {'username': 'staff@example.com', 'password': 'Staff@12345'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.staff.pk)

    def test_first_login_redirects_user_to_setup(self):
        user = self.UserModel.objects.create_user(
            email='temp.staff@example.com',
            password='Temp@12345',
            full_name='Temp Staff',
            phone_number='08000000113',
            username='temp.staff',
            role='staff',
            is_first_login=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('employee_dashboard'))

        self.assertRedirects(response, reverse('first_login_setup'))

    def test_first_login_setup_completes_account_activation(self):
        user = self.UserModel.objects.create_user(
            email='temp2.staff@example.com',
            password='Temp@12345',
            full_name='Temp Staff Two',
            phone_number='08000000114',
            username='temp.staff.two',
            role='staff',
            is_first_login=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('first_login_setup'),
            {
                'email': 'personal.staff@example.com',
                'username': 'personal.staff',
                'new_password1': 'Updated@12345',
                'new_password2': 'Updated@12345',
                'phone_number': '08000000199',
                'display_name': 'Personal Staff',
            },
        )

        user.refresh_from_db()
        self.assertRedirects(response, reverse('employee_dashboard'))
        self.assertFalse(user.is_first_login)
        self.assertEqual(user.email, 'personal.staff@example.com')
        self.assertEqual(user.username, 'personal.staff')
        self.assertTrue(user.check_password('Updated@12345'))
        self.assertIsNotNone(user.password_changed_at)

    def test_admin_reset_password_requires_new_onboarding(self):
        target_user = self.UserModel.objects.create_user(
            email='reset.staff@example.com',
            password='Reset@12345',
            full_name='Reset Staff',
            phone_number='08000000115',
            username='reset.staff',
            role='staff',
            is_first_login=False,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('staff_reset_password', kwargs={'pk': target_user.pk}),
            {'confirm_reset': True},
            follow=True,
        )

        target_user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(target_user.is_first_login)
