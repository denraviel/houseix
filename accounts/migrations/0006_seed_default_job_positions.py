from django.db import migrations


DEFAULT_JOB_POSITIONS = [
    ('Owner', 'owner_position', 'Executive ownership oversight and strategic control.', 'general_management'),
    ('Hotel Administrator', 'hotel_administrator', 'Administrative leadership across hotel operations.', 'general_management'),
    ('Operations Manager', 'operations_manager', 'Cross-functional operational coordination and supervision.', 'general_management'),
    ('Receptionist', 'receptionist', 'Front desk operations, reservations, and guest reception.', 'front_office'),
    ('Front Office Supervisor', 'front_office_supervisor', 'Supervision of front office operations and staff.', 'front_office'),
    ('Cleaner', 'cleaner', 'Room cleaning, housekeeping support, and turnaround duties.', 'housekeeping'),
    ('Housekeeping Supervisor', 'housekeeping_supervisor', 'Supervision of housekeeping teams and room standards.', 'housekeeping'),
    ('Laundry Attendant', 'laundry_attendant', 'Laundry handling, linen processing, and garment support.', 'housekeeping'),
    ('Maintenance Technician', 'maintenance_technician', 'Repair, maintenance execution, and issue resolution.', 'maintenance'),
    ('Maintenance Supervisor', 'maintenance_supervisor', 'Oversight of technical repairs and maintenance teams.', 'maintenance'),
    ('Security Officer', 'security_officer', 'Premises security, patrol, and incident awareness.', 'security'),
    ('Security Supervisor', 'security_supervisor', 'Security team leadership and escalation oversight.', 'security'),
    ('Barman', 'barman', 'Bar service, drink preparation, and bar task execution.', 'food_beverage'),
    ('Bartender', 'bartender', 'Cocktail preparation, beverage service, and guest bar experience.', 'food_beverage'),
    ('Restaurant Attendant', 'restaurant_attendant', 'Restaurant floor service and guest meal support.', 'food_beverage'),
    ('Chef', 'chef', 'Kitchen production, food preparation, and culinary supervision.', 'food_beverage'),
    ('Kitchen Assistant', 'kitchen_assistant', 'Kitchen support, prep work, and cleaning duties.', 'food_beverage'),
    ('Store Keeper', 'store_keeper', 'Storekeeping, stock custody, and issue control.', 'store'),
    ('Procurement Officer', 'procurement_officer', 'Procurement, supplier coordination, and stock replenishment.', 'store'),
    ('Cashier', 'cashier', 'Cash handling, billing support, and payment capture.', 'finance'),
    ('Account Officer', 'account_officer', 'Financial records, reconciliations, and account support.', 'finance'),
    ('Marketing Officer', 'marketing_officer', 'Sales promotion, campaigns, and business development support.', 'sales_marketing'),
    ('Driver', 'driver', 'Transportation and logistics support.', 'driver'),
    ('General Staff', 'general_staff', 'Flexible operational support across general duties.', 'general_staff'),
]


def seed_default_job_positions(apps, schema_editor):
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


def unseed_default_job_positions(apps, schema_editor):
    JobPosition = apps.get_model('accounts', 'JobPosition')
    JobPosition.objects.filter(code__in=[code for _name, code, _description, _department in DEFAULT_JOB_POSITIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_jobposition_customuser_position'),
    ]

    operations = [
        migrations.RunPython(seed_default_job_positions, unseed_default_job_positions),
    ]
