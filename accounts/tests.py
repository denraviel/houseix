from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import CustomUser, JobPosition, ModulePermission
from .services import ModulePermissionService, NavigationService
from tasks.models import MaintenanceCategory, MaintenanceIssue


class ModulePermissionAuthorizationTests(TestCase):
    def setUp(self):
        self.cleaner_position = JobPosition.objects.get(code='cleaner')
        self.housekeeping_manager_position = JobPosition.objects.get(code='housekeeping_supervisor')
        self.sales_module = ModulePermission.objects.get(code='sales')
        self.maintenance_module = ModulePermission.objects.get(code='maintenance')
        self.settings_module = ModulePermission.objects.get(code='settings')
        self.accounts_module = ModulePermission.objects.get(code='accounts')
        self.cleaner = CustomUser.objects.create_user(
            email='cleaner@example.com',
            password='password123',
            full_name='Cleaner User',
            phone_number='08000000901',
            role='staff',
            position=self.cleaner_position,
            is_first_login=False,
        )
        self.manager = CustomUser.objects.create_user(
            email='housekeeping.manager@example.com',
            password='password123',
            full_name='Housekeeping Manager',
            phone_number='08000000902',
            role='manager',
            position=self.housekeeping_manager_position,
            is_first_login=False,
        )

    def test_seeded_module_permissions_exist(self):
        self.assertTrue(ModulePermission.objects.filter(code='dashboard', is_active=True).exists())
        self.assertTrue(ModulePermission.objects.filter(code='reports', is_active=True).exists())
        self.assertTrue(ModulePermission.objects.filter(code='staff_management', is_active=True).exists())

    def test_owner_retains_full_module_access_without_assignment(self):
        owner = CustomUser.objects.create_user(
            email='owner.auth@example.com',
            password='password123',
            full_name='Owner Auth',
            phone_number='08000000903',
            role='owner',
            is_first_login=False,
        )

        modules = NavigationService.get_accessible_modules(owner)

        self.assertIn(NavigationService.MODULE_STAFF_MANAGEMENT, modules)
        self.assertIn(NavigationService.MODULE_REPORTS, modules)
        self.assertIn(NavigationService.MODULE_SETTINGS, modules)

    def test_admin_has_full_access_until_customized(self):
        admin = CustomUser.objects.create_user(
            email='admin.auth@example.com',
            password='password123',
            full_name='Admin Auth',
            phone_number='08000000904',
            role='admin',
            is_first_login=False,
        )

        modules = ModulePermissionService.get_accessible_module_codes(admin)

        self.assertIn(NavigationService.MODULE_REPORTS, modules)
        self.assertIn(NavigationService.MODULE_EXPENSES, modules)
        self.assertIn(NavigationService.MODULE_STAFF_MANAGEMENT, modules)

    def test_admin_can_be_restricted_after_custom_assignment(self):
        admin = CustomUser.objects.create_user(
            email='admin.restricted@example.com',
            password='password123',
            full_name='Restricted Admin',
            phone_number='08000000905',
            role='admin',
            is_first_login=False,
        )

        ModulePermissionService.sync_user_module_permissions(
            user=admin,
            module_permissions=[self.sales_module],
            actor=admin,
        )

        modules = ModulePermissionService.get_accessible_module_codes(admin)

        self.assertIn(self.sales_module.code, modules)
        self.assertIn(self.accounts_module.code, modules)
        self.assertIn(self.settings_module.code, modules)
        self.assertNotIn(NavigationService.MODULE_REPORTS, modules)

    def test_staff_only_has_default_access_without_explicit_permissions(self):
        modules = ModulePermissionService.get_accessible_module_codes(self.cleaner)

        self.assertIn(self.accounts_module.code, modules)
        self.assertIn(self.settings_module.code, modules)
        self.assertIn(NavigationService.MODULE_DASHBOARD, modules)
        self.assertNotIn(self.maintenance_module.code, modules)
        self.assertNotIn(self.sales_module.code, modules)

    def test_positions_do_not_grant_modules_without_assignment(self):
        self.assertFalse(ModulePermissionService.can_access_module(self.cleaner, self.maintenance_module.code))
        self.assertFalse(ModulePermissionService.can_access_module(self.manager, NavigationService.MODULE_REPORTS))

    def test_explicit_module_permissions_drive_access(self):
        ModulePermissionService.sync_user_module_permissions(
            user=self.cleaner,
            module_permissions=[self.sales_module, self.maintenance_module],
            actor=self.cleaner,
        )

        modules = ModulePermissionService.get_accessible_module_codes(self.cleaner)

        self.assertIn(self.sales_module.code, modules)
        self.assertIn(self.maintenance_module.code, modules)
        self.assertIn(self.accounts_module.code, modules)
        self.assertIn(self.settings_module.code, modules)

    def test_module_permission_middleware_blocks_hidden_module(self):
        self.client.force_login(self.cleaner)

        response = self.client.get(reverse('sales_list'))

        self.assertEqual(response.status_code, 403)

    def test_module_permission_middleware_allows_assigned_module(self):
        ModulePermissionService.sync_user_module_permissions(
            user=self.cleaner,
            module_permissions=[self.sales_module],
            actor=self.cleaner,
        )
        self.client.force_login(self.cleaner)

        response = self.client.get(reverse('sales_list'))

        self.assertEqual(response.status_code, 200)


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

    def test_first_login_setup_shows_password_similarity_error(self):
        user = self.UserModel.objects.create_user(
            email='temp3.staff@example.com',
            password='Temp@12345',
            full_name='Temp Staff Three',
            phone_number='08000000116',
            username='temp.staff.three',
            role='staff',
            is_first_login=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('first_login_setup'),
            {
                'email': 'personalthree.staff@example.com',
                'username': 'john.doe',
                'new_password1': 'john.doe@123',
                'new_password2': 'john.doe@123',
                'phone_number': '08000000188',
                'display_name': 'John Three',
            },
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The password is too similar to the username.')
        self.assertTrue(user.is_first_login)

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


class StaffDeletionTests(TestCase):
    def setUp(self):
        self.UserModel = get_user_model()
        self.owner = self.UserModel.objects.create_user(
            email='owner.delete@example.com',
            password='Owner@12345',
            full_name='Owner Delete',
            phone_number='08000000121',
            username='owner.delete',
            role='owner',
            is_first_login=False,
        )
        self.staff = self.UserModel.objects.create_user(
            email='staff.delete@example.com',
            password='Staff@12345',
            full_name='Referenced Staff',
            phone_number='08000000122',
            username='staff.delete',
            role='staff',
            is_first_login=False,
        )
        self.category = MaintenanceCategory.objects.create(
            name='Deletion Test Category',
            description='Used for protected delete tests.',
            is_active=True,
        )

    def test_delete_staff_with_protected_maintenance_reference_shows_message(self):
        MaintenanceIssue.objects.create(
            issue_number='MTNDELETE001',
            title='Protected Reporter',
            description='This issue preserves the reporting user.',
            category=self.category,
            reported_by=self.staff,
            priority=MaintenanceIssue.PRIORITY_MEDIUM,
            status=MaintenanceIssue.STATUS_REPORTED,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('staff_delete', kwargs={'pk': self.staff.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.UserModel.objects.filter(pk=self.staff.pk).exists())
        messages = [message.message for message in response.context['messages']]
        self.assertIn(
            'This user cannot be deleted because they are referenced by operational records. Deactivate the account instead to preserve audit history.',
            messages,
        )
