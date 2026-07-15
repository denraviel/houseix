import secrets

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .models import AuditLog, CustomUser, JobPosition, ModulePermission


class ModulePermissionService:
    DEFAULT_ALWAYS_AVAILABLE_CODES = {'dashboard', 'accounts', 'settings'}

    @classmethod
    def active_modules_queryset(cls):
        return ModulePermission.objects.filter(is_active=True).order_by('display_order', 'name')

    @classmethod
    def active_modules_by_code(cls):
        return {module.code: module for module in cls.active_modules_queryset()}

    @classmethod
    def get_explicit_module_codes(cls, user):
        if not getattr(user, 'is_authenticated', False):
            return set()
        return set(
            user.module_permissions.filter(is_active=True).values_list('code', flat=True)
        )

    @classmethod
    def get_accessible_module_codes(cls, user):
        if not getattr(user, 'is_authenticated', False):
            return set()
        active_codes = set(cls.active_modules_by_code())
        if not active_codes:
            return set()
        if getattr(user, 'role', '') == 'owner':
            return active_codes
        default_codes = active_codes & cls.DEFAULT_ALWAYS_AVAILABLE_CODES
        explicit_codes = cls.get_explicit_module_codes(user) & active_codes
        if getattr(user, 'role', '') == 'admin' and not getattr(user, 'module_permissions_configured', False):
            return active_codes
        return default_codes | explicit_codes

    @classmethod
    def can_access_module(cls, user, module_code):
        return module_code in cls.get_accessible_module_codes(user)

    @staticmethod
    def resolve_dashboard_url_name(user):
        return 'admin_dashboard' if getattr(user, 'role', '') in ['owner', 'admin', 'manager'] else 'employee_dashboard'

    @classmethod
    def resolve_module_url_name(cls, module, user):
        if module.code == 'dashboard':
            return cls.resolve_dashboard_url_name(user)
        if module.code == 'performance':
            return 'my_performance' if getattr(user, 'role', '') == 'staff' else 'performance_reports'
        return module.module_url_name or ''

    @classmethod
    def get_menu_items(cls, user):
        accessible_codes = cls.get_accessible_module_codes(user)
        items = []
        excluded_codes = {'accounts', 'settings'}
        for module in cls.active_modules_queryset():
            if module.code not in accessible_codes or module.code in excluded_codes:
                continue
            url_name = cls.resolve_module_url_name(module, user)
            if not url_name:
                continue
            try:
                url = reverse(url_name)
            except NoReverseMatch:
                continue
            items.append(
                {
                    'code': module.code,
                    'label': module.name,
                    'icon': module.icon,
                    'url_name': url_name,
                    'url': url,
                }
            )
        return items

    @classmethod
    def get_dashboard_widgets(cls, user):
        accessible_codes = cls.get_accessible_module_codes(user)
        widgets = []
        excluded_codes = {'dashboard', 'accounts', 'settings', 'audit_logs', 'activity_logs', 'administration'}
        for module in cls.active_modules_queryset():
            if module.code not in accessible_codes or module.code in excluded_codes:
                continue
            url_name = cls.resolve_module_url_name(module, user)
            if not url_name:
                continue
            try:
                url = reverse(url_name)
            except NoReverseMatch:
                continue
            widgets.append(
                {
                    'code': module.code,
                    'title': module.name,
                    'subtitle': module.description or f'Open the {module.name.lower()} workspace.',
                    'icon': module.icon,
                    'url_name': url_name,
                    'url': url,
                }
            )
        return widgets[:6]

    @classmethod
    @transaction.atomic
    def sync_user_module_permissions(cls, *, user, module_permissions, actor):
        desired_permissions = list(
            ModulePermission.objects.filter(
                pk__in=[permission.pk for permission in module_permissions],
                is_active=True,
            ).order_by('display_order', 'name')
        )
        existing_codes = set(user.module_permissions.filter(is_active=True).values_list('code', flat=True))
        desired_codes = {permission.code for permission in desired_permissions}

        user.module_permissions.set(desired_permissions)
        if not user.module_permissions_configured:
            user.module_permissions_configured = True
            user.save(update_fields=['module_permissions_configured'])

        granted = sorted(desired_codes - existing_codes)
        revoked = sorted(existing_codes - desired_codes)
        for module_code in granted:
            AuditLog.log(actor, 'module_permission_granted', f'Granted {module_code} access to {user.email}.')
        for module_code in revoked:
            AuditLog.log(actor, 'module_permission_revoked', f'Revoked {module_code} access from {user.email}.')

        summary = ', '.join(sorted(desired_codes)) if desired_codes else 'default-only access'
        AuditLog.log(actor, 'user_module_permissions_updated', f'Updated module permissions for {user.email}: {summary}.')
        return user


class NavigationService:
    MODULE_DASHBOARD = 'dashboard'
    MODULE_REPORTS = 'reports'
    MODULE_EXPENSES = 'expenses'
    MODULE_SALES = 'sales'
    MODULE_INVENTORY = 'inventory'
    MODULE_PRODUCTS = 'products'
    MODULE_INVOICES = 'invoices'
    MODULE_CUSTOMERS = 'customers'
    MODULE_ROOMS = 'rooms'
    MODULE_STAYS = 'stays'
    MODULE_TASKS = 'tasks'
    MODULE_MY_TASKS = 'my_tasks'
    MODULE_INSPECTIONS = 'inspections'
    MODULE_MAINTENANCE = 'maintenance'
    MODULE_PERFORMANCE = 'performance'
    MODULE_STAFF_MANAGEMENT = 'staff_management'
    MODULE_ACCOUNTS = 'accounts'
    MODULE_SETTINGS = 'settings'
    MODULE_AUDIT_LOGS = 'audit_logs'
    MODULE_ACTIVITY_LOGS = 'activity_logs'
    MODULE_ADMINISTRATION = 'administration'

    URL_NAME_TO_MODULE = {
        'home': MODULE_DASHBOARD,
        'admin_dashboard': MODULE_DASHBOARD,
        'employee_dashboard': MODULE_DASHBOARD,
        'profile': MODULE_ACCOUNTS,
        'profile_edit': MODULE_ACCOUNTS,
        'account_settings': MODULE_SETTINGS,
        'change_password': MODULE_SETTINGS,
        'change_email': MODULE_SETTINGS,
        'change_username': MODULE_SETTINGS,
        'staff_list': MODULE_STAFF_MANAGEMENT,
        'staff_create': MODULE_STAFF_MANAGEMENT,
        'staff_edit': MODULE_STAFF_MANAGEMENT,
        'staff_reset_password': MODULE_STAFF_MANAGEMENT,
        'staff_delete': MODULE_STAFF_MANAGEMENT,
        'toggle_staff_active': MODULE_STAFF_MANAGEMENT,
        'product_list': MODULE_PRODUCTS,
        'product_create': MODULE_PRODUCTS,
        'product_update': MODULE_PRODUCTS,
        'product_toggle_active': MODULE_PRODUCTS,
        'product_delete': MODULE_PRODUCTS,
        'inventory_list': MODULE_INVENTORY,
        'inventory_item_create': MODULE_INVENTORY,
        'inventory_item_edit': MODULE_INVENTORY,
        'inventory_item_delete': MODULE_INVENTORY,
        'add_stock': MODULE_INVENTORY,
        'stock_movement_create': MODULE_INVENTORY,
        'sales_list': MODULE_SALES,
        'sale_create': MODULE_SALES,
        'sale_delete': MODULE_SALES,
        'customer_list': MODULE_CUSTOMERS,
        'customer_create': MODULE_CUSTOMERS,
        'customer_detail': MODULE_CUSTOMERS,
        'customer_update': MODULE_CUSTOMERS,
        'customer_delete': MODULE_CUSTOMERS,
        'room_list': MODULE_ROOMS,
        'room_create': MODULE_ROOMS,
        'room_update': MODULE_ROOMS,
        'room_delete': MODULE_ROOMS,
        'room_change_status': MODULE_ROOMS,
        'stay_list': MODULE_STAYS,
        'stay_create': MODULE_STAYS,
        'stay_detail': MODULE_STAYS,
        'stay_update': MODULE_STAYS,
        'stay_status_update': MODULE_STAYS,
        'invoice_list': MODULE_INVOICES,
        'invoice_create': MODULE_INVOICES,
        'invoice_history': MODULE_INVOICES,
        'invoice_generate': MODULE_INVOICES,
        'invoice_detail': MODULE_INVOICES,
        'invoice_update': MODULE_INVOICES,
        'invoice_payment': MODULE_INVOICES,
        'invoice_print': MODULE_INVOICES,
        'invoice_pdf': MODULE_INVOICES,
        'expense_dashboard': MODULE_EXPENSES,
        'expense_list': MODULE_EXPENSES,
        'expense_create': MODULE_EXPENSES,
        'expense_detail': MODULE_EXPENSES,
        'expense_update': MODULE_EXPENSES,
        'expense_delete': MODULE_EXPENSES,
        'expense_approval': MODULE_EXPENSES,
        'expense_category_list': MODULE_EXPENSES,
        'expense_category_create': MODULE_EXPENSES,
        'vendor_list': MODULE_EXPENSES,
        'vendor_create': MODULE_EXPENSES,
        'recurring_expense_list': MODULE_EXPENSES,
        'recurring_expense_create': MODULE_EXPENSES,
        'recurring_expense_generate': MODULE_EXPENSES,
        'fuel_log_list': MODULE_EXPENSES,
        'fuel_log_create': MODULE_EXPENSES,
        'task_list': MODULE_TASKS,
        'task_create': MODULE_TASKS,
        'task_update': MODULE_TASKS,
        'task_delete': MODULE_TASKS,
        'my_tasks': MODULE_MY_TASKS,
        'staff_task_start': MODULE_MY_TASKS,
        'staff_task_complete': MODULE_MY_TASKS,
        'staff_task_update': MODULE_MY_TASKS,
        'maintenance_dashboard': MODULE_MAINTENANCE,
        'maintenance_issue_list': MODULE_MAINTENANCE,
        'maintenance_issue_create': MODULE_MAINTENANCE,
        'maintenance_issue_detail': MODULE_MAINTENANCE,
        'maintenance_issue_update': MODULE_MAINTENANCE,
        'maintenance_issue_assign': MODULE_MAINTENANCE,
        'maintenance_issue_verify': MODULE_MAINTENANCE,
        'maintenance_issue_escalate': MODULE_MAINTENANCE,
        'maintenance_issue_record_expense': MODULE_MAINTENANCE,
        'maintenance_category_list': MODULE_MAINTENANCE,
        'maintenance_category_create': MODULE_MAINTENANCE,
        'maintenance_activity_list': MODULE_MAINTENANCE,
        'inspection_list': MODULE_INSPECTIONS,
        'inspection_history': MODULE_INSPECTIONS,
        'inspection_detail': MODULE_INSPECTIONS,
        'inspection_update': MODULE_INSPECTIONS,
        'inspection_submit': MODULE_INSPECTIONS,
        'inspection_create': MODULE_INSPECTIONS,
        'my_performance': MODULE_PERFORMANCE,
        'performance_dashboard': MODULE_PERFORMANCE,
        'performance_reports': MODULE_PERFORMANCE,
        'staff_performance_detail': MODULE_PERFORMANCE,
        'performance_rating_create': MODULE_PERFORMANCE,
        'reports_dashboard': MODULE_REPORTS,
        'sales_report': MODULE_REPORTS,
        'inventory_report': MODULE_REPORTS,
        'product_performance_report': MODULE_REPORTS,
        'staff_performance_report': MODULE_REPORTS,
        'activity_report': MODULE_REPORTS,
    }

    @staticmethod
    def _user_positions(user):
        if not getattr(user, 'is_authenticated', False):
            return []
        if hasattr(user, '_ordered_positions'):
            return user._ordered_positions()
        return list(user.positions.filter(is_active=True).order_by('department', 'name'))

    @classmethod
    def get_accessible_modules(cls, user):
        return ModulePermissionService.get_accessible_module_codes(user)

    @classmethod
    def can_access_module(cls, user, module_code):
        return ModulePermissionService.can_access_module(user, module_code)

    @classmethod
    def get_module_for_url_name(cls, url_name):
        module_code = cls.URL_NAME_TO_MODULE.get(url_name)
        if module_code:
            return module_code
        try:
            return ModulePermission.objects.get(is_active=True, module_url_name=url_name).code
        except ModulePermission.DoesNotExist:
            return None

    @classmethod
    def can_access_url_name(cls, user, url_name):
        module_code = cls.get_module_for_url_name(url_name)
        if not module_code:
            return True
        return cls.can_access_module(user, module_code)

    @staticmethod
    def get_dashboard_url_name(user):
        return ModulePermissionService.resolve_dashboard_url_name(user)

    @staticmethod
    def get_performance_url_name(user):
        return 'my_performance' if getattr(user, 'role', '') == 'staff' else 'performance_reports'

    @classmethod
    def get_dashboard_title(cls, user):
        positions = cls._user_positions(user)
        if positions:
            if len(positions) == 1:
                return f'{positions[0].name} Dashboard'
            return 'Multi-Position Dashboard'
        role = getattr(user, 'get_role_display', None)
        return f'{role() if callable(role) else "User"} Dashboard'

    @classmethod
    def get_menu_items(cls, user):
        return ModulePermissionService.get_menu_items(user)

    @classmethod
    def get_dashboard_widgets(cls, user):
        return ModulePermissionService.get_dashboard_widgets(user)


class AccountProfileService:
    @staticmethod
    def normalize_username(username):
        return (username or '').strip().lower()

    @staticmethod
    def normalize_email(email):
        return (email or '').strip().lower()

    @classmethod
    def validate_username(cls, *, username, user=None):
        username = cls.normalize_username(username)
        if not username:
            raise ValidationError('Username is required.')
        CustomUser._meta.get_field('username').run_validators(username)
        queryset = CustomUser.objects.exclude(pk=getattr(user, 'pk', None)).filter(username__iexact=username)
        if queryset.exists():
            raise ValidationError('This username is already in use.')
        return username

    @classmethod
    def validate_email(cls, *, email, user=None):
        email = cls.normalize_email(email)
        if not email:
            raise ValidationError('Email address is required.')
        queryset = CustomUser.objects.exclude(pk=getattr(user, 'pk', None)).filter(email__iexact=email)
        if queryset.exists():
            raise ValidationError('This email address is already in use.')
        return email

    @classmethod
    @transaction.atomic
    def update_profile(cls, *, user, cleaned_data):
        previous_email = user.email
        previous_username = user.username
        previous_photo = bool(user.profile_photo)

        if 'display_name' in cleaned_data:
            user.display_name = cleaned_data.get('display_name', '').strip()
        if 'phone_number' in cleaned_data:
            user.phone_number = (cleaned_data.get('phone_number') or '').strip()
        if 'profile_photo' in cleaned_data and cleaned_data.get('profile_photo'):
            user.profile_photo = cleaned_data['profile_photo']
        if 'username' in cleaned_data:
            user.username = cls.validate_username(username=cleaned_data.get('username'), user=user)
        if 'email' in cleaned_data:
            user.email = cls.validate_email(email=cleaned_data.get('email'), user=user)
        user.save()

        AuditLog.log(user, 'profile_updated', f'Updated profile for {user.email}.')
        if previous_photo != bool(user.profile_photo):
            AuditLog.log(user, 'profile_photo_updated', f'Updated profile photo for {user.email}.')
        if previous_email != user.email:
            AuditLog.log(user, 'email_changed', f'Changed email address for {user.full_name}.')
        if previous_username != user.username:
            AuditLog.log(user, 'username_changed', f'Changed username for {user.full_name}.')
        return user

    @classmethod
    def update_email(cls, *, user, email):
        user.email = cls.validate_email(email=email, user=user)
        user.save(update_fields=['email'])
        AuditLog.log(user, 'email_changed', f'Changed email address for {user.full_name}.')
        return user

    @classmethod
    def update_username(cls, *, user, username):
        user.username = cls.validate_username(username=username, user=user)
        user.save(update_fields=['username'])
        AuditLog.log(user, 'username_changed', f'Changed username for {user.full_name}.')
        return user


class AccountSecurityService:
    TEMP_PASSWORD_SPECIALS = '!@#$%&*?'

    @classmethod
    def generate_temporary_password(cls, length=12):
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
        password = [
            secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ'),
            secrets.choice('abcdefghijkmnopqrstuvwxyz'),
            secrets.choice('23456789'),
            secrets.choice(cls.TEMP_PASSWORD_SPECIALS),
        ]
        while len(password) < length:
            password.append(secrets.choice(alphabet + cls.TEMP_PASSWORD_SPECIALS))
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)

    @staticmethod
    def validate_password(*, password, user):
        password_validation.validate_password(password, user=user)
        return password

    @classmethod
    def set_password(cls, *, user, password, actor=None, first_login_required=False):
        cls.validate_password(password=password, user=user)
        user.set_password(password)
        user.password_changed_at = timezone.now()
        user.is_first_login = first_login_required
        user.save(update_fields=['password', 'password_changed_at', 'is_first_login'])
        AuditLog.log(actor or user, 'password_changed', f'Updated password for {user.email}.')
        return user

    @classmethod
    def reset_password(cls, *, user, actor):
        temporary_password = cls.generate_temporary_password()
        user.set_password(temporary_password)
        user.is_first_login = True
        user.password_changed_at = timezone.now()
        user.save(update_fields=['password', 'is_first_login', 'password_changed_at'])
        AuditLog.log(actor, 'password_reset', f'Reset password for {user.email}.')
        return temporary_password


class AccountOnboardingService:
    @staticmethod
    def requires_onboarding(user):
        return bool(getattr(user, 'is_authenticated', False) and getattr(user, 'is_first_login', False))

    @staticmethod
    def onboarding_exempt_url_names():
        return {
            'login',
            'logout',
            'first_login_setup',
        }

    @staticmethod
    def get_post_login_redirect_url(user):
        return reverse(NavigationService.get_dashboard_url_name(user))

    @classmethod
    @transaction.atomic
    def create_staff_account(cls, *, cleaned_data, actor):
        user = CustomUser(
            full_name=cleaned_data['full_name'].strip(),
            display_name=(cleaned_data.get('display_name') or '').strip(),
            username=AccountProfileService.validate_username(username=cleaned_data['username']),
            email=AccountProfileService.validate_email(email=cleaned_data['email']),
            phone_number=(cleaned_data.get('phone_number') or '').strip(),
            role=cleaned_data['role'],
            is_active=True,
            is_first_login=True,
            email_verified=False,
        )
        password = cleaned_data['password1']
        AccountSecurityService.validate_password(password=password, user=user)
        user.set_password(password)
        user.password_changed_at = timezone.now()
        user.save()
        user.positions.set(cleaned_data.get('positions') or [])
        if 'module_permissions' in cleaned_data:
            selected_permissions = cleaned_data.get('module_permissions') or []
            if not (user.role == 'admin' and not selected_permissions):
                ModulePermissionService.sync_user_module_permissions(
                    user=user,
                    module_permissions=selected_permissions,
                    actor=actor,
                )
        AuditLog.log(actor, 'user_created', f'Created user {user.email} ({user.role}).')
        return user

    @classmethod
    @transaction.atomic
    def update_staff_account(cls, *, user, cleaned_data, actor):
        user.full_name = cleaned_data['full_name'].strip()
        user.display_name = (cleaned_data.get('display_name') or '').strip()
        user.username = AccountProfileService.validate_username(username=cleaned_data['username'], user=user)
        user.email = AccountProfileService.validate_email(email=cleaned_data['email'], user=user)
        user.phone_number = (cleaned_data.get('phone_number') or '').strip()
        user.role = cleaned_data['role']
        user.is_active = cleaned_data['is_active']
        user.save()
        user.positions.set(cleaned_data.get('positions') or [])
        if 'module_permissions' in cleaned_data:
            ModulePermissionService.sync_user_module_permissions(
                user=user,
                module_permissions=cleaned_data.get('module_permissions') or [],
                actor=actor,
            )
        AuditLog.log(actor, 'user_edited', f'Edited user {user.email} ({user.role}).')
        return user

    @classmethod
    @transaction.atomic
    def complete_first_login(cls, *, user, cleaned_data):
        previous_email = user.email
        previous_username = user.username
        previous_photo = bool(user.profile_photo)
        user.display_name = (cleaned_data.get('display_name') or '').strip()
        user.phone_number = (cleaned_data.get('phone_number') or '').strip()
        if cleaned_data.get('profile_photo'):
            user.profile_photo = cleaned_data['profile_photo']
        user.username = AccountProfileService.validate_username(username=cleaned_data['username'], user=user)
        user.email = AccountProfileService.validate_email(email=cleaned_data['email'], user=user)
        new_password = cleaned_data['new_password1']
        AccountSecurityService.validate_password(password=new_password, user=user)
        user.set_password(new_password)
        user.is_first_login = False
        user.password_changed_at = timezone.now()
        user.save()
        AuditLog.log(user, 'profile_updated', f'Updated onboarding profile for {user.email}.')
        if previous_photo != bool(user.profile_photo):
            AuditLog.log(user, 'profile_photo_updated', f'Updated profile photo for {user.email}.')
        if previous_email != user.email:
            AuditLog.log(user, 'email_changed', f'Changed email address for {user.full_name}.')
        if previous_username != user.username:
            AuditLog.log(user, 'username_changed', f'Changed username for {user.full_name}.')
        AuditLog.log(user, 'password_changed', f'Updated password for {user.email}.')
        AuditLog.log(user, 'first_login_completed', f'Completed first login setup for {user.email}.')
        return user
