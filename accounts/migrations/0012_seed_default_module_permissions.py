from django.db import migrations


DEFAULT_MODULE_PERMISSIONS = [
    ('Dashboard', 'dashboard', 'Primary landing area for each authenticated user.', '', 'bi-speedometer2', 10),
    ('Reports', 'reports', 'Management reporting and analytics workspace.', 'reports_dashboard', 'bi-graph-up', 20),
    ('Expenses', 'expenses', 'Operational expense entry, approval, and tracking.', 'expense_dashboard', 'bi-receipt', 30),
    ('Sales', 'sales', 'Point-of-sale and guest product sales workflows.', 'sales_list', 'bi-cash-stack', 40),
    ('Inventory', 'inventory', 'Inventory records, stock additions, and movements.', 'inventory_list', 'bi-box-seam', 50),
    ('Products', 'products', 'Product catalog and availability management.', 'product_list', 'bi-basket', 60),
    ('Invoices', 'invoices', 'Guest billing, invoice history, and payment handling.', 'invoice_list', 'bi-file-earmark-text', 70),
    ('Customers', 'customers', 'Guest and customer records.', 'customer_list', 'bi-people', 80),
    ('Rooms', 'rooms', 'Room inventory and status management.', 'room_list', 'bi-door-open', 90),
    ('Guest Stays', 'stays', 'Reservations, check-in, check-out, and live stays.', 'stay_list', 'bi-calendar-check', 100),
    ('Tasks', 'tasks', 'Department task assignment and oversight.', 'task_list', 'bi-list-task', 110),
    ('My Tasks', 'my_tasks', 'Personal assigned tasks and work updates.', 'my_tasks', 'bi-check2-square', 120),
    ('Inspections', 'inspections', 'Operational inspections and checklist reviews.', 'inspection_list', 'bi-clipboard-check', 130),
    ('Maintenance', 'maintenance', 'Maintenance issues, assignments, and verification.', 'maintenance_dashboard', 'bi-tools', 140),
    ('Performance', 'performance', 'Performance tracking and ratings.', 'performance_dashboard', 'bi-bar-chart', 150),
    ('Staff Management', 'staff_management', 'Staff onboarding, editing, and account administration.', 'staff_list', 'bi-person-gear', 160),
    ('Accounts', 'accounts', 'Personal profile and account information.', 'profile', 'bi-person-circle', 170),
    ('Settings', 'settings', 'Account settings and security preferences.', 'account_settings', 'bi-gear', 180),
    ('Audit Logs', 'audit_logs', 'Audit and accountability log access.', '', 'bi-shield-check', 190),
    ('Activity Logs', 'activity_logs', 'Operational activity log access.', '', 'bi-clock-history', 200),
    ('Administration', 'administration', 'System administration and privileged configuration.', '', 'bi-sliders', 210),
]


def seed_default_module_permissions(apps, schema_editor):
    ModulePermission = apps.get_model('accounts', 'ModulePermission')
    for name, code, description, module_url_name, icon, display_order in DEFAULT_MODULE_PERMISSIONS:
        ModulePermission.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': description,
                'module_url_name': module_url_name,
                'icon': icon,
                'display_order': display_order,
                'is_active': True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0011_customuser_module_permissions_configured_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_module_permissions, migrations.RunPython.noop),
    ]
