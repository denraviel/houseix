from django.db import migrations


# New position to fill the gap: nothing currently supervises Barman/Bartender.
NEW_POSITIONS = [
    ('Bar Supervisor', 'bar_supervisor', 'Bar team leadership and shift supervision.', 'food_beverage'),
]

# code -> list of codes it is authorized to assign tasks to (direct edges;
# authority is transitive at runtime, so Operations Manager also reaches
# anyone a Bar Supervisor manages, without needing every edge listed here).
AUTHORITY_EDGES = {
    'operations_manager': [
        'front_office_supervisor', 'receptionist',
        'housekeeping_supervisor', 'cleaner', 'laundry_attendant',
        'maintenance_supervisor', 'maintenance_technician',
        'security_supervisor', 'security_officer',
        'bar_supervisor', 'barman', 'bartender', 'restaurant_attendant', 'chef', 'kitchen_assistant',
        'store_keeper', 'procurement_officer',
        'account_officer', 'cashier',
        'marketing_officer', 'driver', 'general_staff',
    ],
    'hotel_administrator': [
        'operations_manager',
        'front_office_supervisor', 'receptionist',
        'housekeeping_supervisor', 'cleaner', 'laundry_attendant',
        'maintenance_supervisor', 'maintenance_technician',
        'security_supervisor', 'security_officer',
        'bar_supervisor', 'barman', 'bartender', 'restaurant_attendant', 'chef', 'kitchen_assistant',
        'store_keeper', 'procurement_officer',
        'account_officer', 'cashier',
        'marketing_officer', 'driver', 'general_staff',
    ],
    'front_office_supervisor': ['receptionist'],
    'housekeeping_supervisor': ['cleaner', 'laundry_attendant'],
    'maintenance_supervisor': ['maintenance_technician'],
    'security_supervisor': ['security_officer'],
    'bar_supervisor': ['barman', 'bartender', 'restaurant_attendant'],
    'chef': ['kitchen_assistant'],
    'account_officer': ['cashier'],
}


def seed_position_authority(apps, schema_editor):
    JobPosition = apps.get_model('accounts', 'JobPosition')

    for name, code, description, department in NEW_POSITIONS:
        JobPosition.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': description,
                'department': department,
                'is_active': True,
            },
        )

    for manager_code, subordinate_codes in AUTHORITY_EDGES.items():
        try:
            manager_position = JobPosition.objects.get(code=manager_code)
        except JobPosition.DoesNotExist:
            continue
        subordinate_ids = list(
            JobPosition.objects.filter(code__in=subordinate_codes).values_list('pk', flat=True)
        )
        manager_position.manages_positions.add(*subordinate_ids)


def unseed_position_authority(apps, schema_editor):
    JobPosition = apps.get_model('accounts', 'JobPosition')

    for manager_code, subordinate_codes in AUTHORITY_EDGES.items():
        try:
            manager_position = JobPosition.objects.get(code=manager_code)
        except JobPosition.DoesNotExist:
            continue
        subordinate_ids = list(
            JobPosition.objects.filter(code__in=subordinate_codes).values_list('pk', flat=True)
        )
        manager_position.manages_positions.remove(*subordinate_ids)

    JobPosition.objects.filter(code__in=[code for _n, code, _d, _dep in NEW_POSITIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_jobposition_manages_positions'),
    ]

    operations = [
        migrations.RunPython(seed_position_authority, unseed_position_authority),
    ]
