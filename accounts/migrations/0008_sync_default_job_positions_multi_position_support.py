from django.db import migrations


DEFAULT_JOB_POSITIONS = [
    ('Hotel Administrator', 'hotel_administrator', 'Administrative leadership across hotel operations.', 'general_management'),
    ('Operations Manager', 'operations_manager', 'Cross-functional operational coordination and supervision.', 'general_management'),
    ('Cleaner', 'cleaner', 'Room cleaning, housekeeping support, and turnaround duties.', 'housekeeping'),
    ('Housekeeping Supervisor', 'housekeeping_supervisor', 'Supervision of housekeeping teams and room standards.', 'housekeeping'),
    ('Laundry Attendant', 'laundry_attendant', 'Laundry handling, linen processing, and garment support.', 'housekeeping'),
    ('Barman', 'barman', 'Bar service, drink preparation, and bar task execution.', 'food_beverage'),
    ('Bartender', 'bartender', 'Cocktail preparation, beverage service, and guest bar experience.', 'food_beverage'),
    ('Restaurant Attendant', 'restaurant_attendant', 'Restaurant floor service and guest meal support.', 'food_beverage'),
    ('Kitchen Assistant', 'kitchen_assistant', 'Kitchen support, prep work, and cleaning duties.', 'food_beverage'),
    ('Chef', 'chef', 'Kitchen production, food preparation, and culinary supervision.', 'food_beverage'),
    ('Receptionist', 'receptionist', 'Front desk operations, reservations, and guest reception.', 'front_office'),
    ('Front Office Supervisor', 'front_office_supervisor', 'Supervision of front office operations and staff.', 'front_office'),
    ('Maintenance Technician', 'maintenance_technician', 'Repair, maintenance execution, and issue resolution.', 'maintenance'),
    ('Maintenance Supervisor', 'maintenance_supervisor', 'Oversight of technical repairs and maintenance teams.', 'maintenance'),
    ('Security Officer', 'security_officer', 'Premises security, patrol, and incident awareness.', 'security'),
    ('Security Supervisor', 'security_supervisor', 'Security team leadership and escalation oversight.', 'security'),
    ('Cashier', 'cashier', 'Cash handling, billing support, and payment capture.', 'finance'),
    ('Account Officer', 'account_officer', 'Financial records, reconciliations, and account support.', 'finance'),
    ('Store Keeper', 'store_keeper', 'Storekeeping, stock custody, and issue control.', 'store'),
    ('Procurement Officer', 'procurement_officer', 'Procurement, supplier coordination, and stock replenishment.', 'store'),
    ('Driver', 'driver', 'Transportation and logistics support.', 'driver'),
    ('General Staff', 'general_staff', 'Flexible operational support across general duties.', 'general_staff'),
]


def sync_default_job_positions(apps, schema_editor):
    JobPosition = apps.get_model('accounts', 'JobPosition')
    for name, code, description, department in DEFAULT_JOB_POSITIONS:
        JobPosition.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': description,
                'department': department,
                'is_active': True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0007_remove_customuser_position_customuser_positions'),
    ]

    operations = [
        migrations.RunPython(sync_default_job_positions, migrations.RunPython.noop),
    ]
