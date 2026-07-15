from django.db import migrations


LEGACY_STAFF_FALLBACK_MODULES = {
    'dashboard',
    'sales',
    'inventory',
    'customers',
    'rooms',
    'stays',
    'invoices',
    'expenses',
    'my_tasks',
    'maintenance',
    'performance',
}

LEGACY_MANAGER_FALLBACK_MODULES = {
    'dashboard',
    'staff_management',
    'products',
    'inventory',
    'sales',
    'customers',
    'rooms',
    'stays',
    'invoices',
    'expenses',
    'tasks',
    'maintenance',
    'inspections',
    'performance',
    'reports',
}

LEGACY_STAFF_DEPARTMENT_MODULES = {
    'front_office': {'dashboard', 'stays', 'customers', 'rooms', 'invoices', 'my_tasks'},
    'housekeeping': {'dashboard', 'my_tasks', 'maintenance', 'performance'},
    'maintenance': {'dashboard', 'my_tasks', 'maintenance', 'performance'},
    'security': {'dashboard', 'my_tasks', 'maintenance'},
    'food_beverage': {'dashboard', 'sales', 'inventory', 'my_tasks'},
    'store': {'dashboard', 'inventory', 'products', 'my_tasks'},
    'finance': {'dashboard', 'invoices', 'expenses', 'reports', 'my_tasks'},
    'sales_marketing': {'dashboard', 'sales', 'customers', 'reports', 'my_tasks'},
    'driver': {'dashboard', 'my_tasks'},
    'general_staff': {'dashboard', 'my_tasks', 'performance'},
    'general_management': LEGACY_STAFF_FALLBACK_MODULES,
}

LEGACY_MANAGER_DEPARTMENT_MODULES = {
    'general_management': LEGACY_MANAGER_FALLBACK_MODULES,
    'front_office': {'dashboard', 'customers', 'rooms', 'stays', 'invoices', 'tasks', 'reports'},
    'housekeeping': {'dashboard', 'tasks', 'inspections', 'maintenance', 'performance', 'reports'},
    'maintenance': {'dashboard', 'tasks', 'maintenance', 'performance', 'reports'},
    'security': {'dashboard', 'tasks', 'maintenance', 'reports'},
    'food_beverage': {'dashboard', 'products', 'inventory', 'sales', 'tasks', 'reports'},
    'store': {'dashboard', 'products', 'inventory', 'tasks', 'reports'},
    'finance': {'dashboard', 'invoices', 'expenses', 'reports', 'tasks'},
    'sales_marketing': {'dashboard', 'customers', 'sales', 'reports', 'tasks'},
    'driver': {'dashboard', 'tasks'},
    'general_staff': {'dashboard', 'tasks', 'reports'},
}


def _legacy_modules_for_user(user, positions):
    if user.role == 'owner':
        return set()
    if user.role == 'admin':
        return None
    if user.role == 'manager':
        if not positions:
            return set(LEGACY_MANAGER_FALLBACK_MODULES)
        modules = {'dashboard', 'tasks'}
        for position in positions:
            modules.update(LEGACY_MANAGER_DEPARTMENT_MODULES.get(position.department, {'dashboard', 'tasks'}))
        return modules
    if not positions:
        return set(LEGACY_STAFF_FALLBACK_MODULES)
    modules = {'dashboard', 'my_tasks'}
    for position in positions:
        modules.update(LEGACY_STAFF_DEPARTMENT_MODULES.get(position.department, {'dashboard', 'my_tasks'}))
    return modules


def backfill_module_permissions(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    ModulePermission = apps.get_model('accounts', 'ModulePermission')

    modules_by_code = {module.code: module for module in ModulePermission.objects.filter(is_active=True)}
    all_modules = list(modules_by_code.values())

    for user in CustomUser.objects.all():
        positions = list(user.positions.filter(is_active=True).order_by('department', 'name'))
        legacy_modules = _legacy_modules_for_user(user, positions)

        if user.role == 'owner':
            continue

        if legacy_modules is None:
            user.module_permissions.set(all_modules)
        else:
            selected_modules = [modules_by_code[code] for code in legacy_modules if code in modules_by_code]
            user.module_permissions.set(selected_modules)

        user.module_permissions_configured = True
        user.save(update_fields=['module_permissions_configured'])


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0012_seed_default_module_permissions'),
    ]

    operations = [
        migrations.RunPython(backfill_module_permissions, migrations.RunPython.noop),
    ]
