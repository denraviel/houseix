from django.db import migrations


DEFAULT_MAINTENANCE_CATEGORIES = [
    ('Electrical', 'Power supply, wiring, lighting, sockets, and related electrical issues.'),
    ('Plumbing', 'Water supply, pipes, drainage, taps, and leak-related issues.'),
    ('Painting', 'Wall finishing, repainting, touch-ups, and paint damage concerns.'),
    ('Air Conditioning', 'Cooling, ventilation, and AC servicing or repair issues.'),
    ('Furniture', 'Beds, chairs, tables, wardrobes, and other furniture repairs.'),
    ('Generator', 'Generator operation, servicing, leakage, and power backup concerns.'),
    ('Television', 'Television setup, signal, display, and device repair issues.'),
    ('Internet', 'Wi-Fi, connectivity, router, and network-related faults.'),
    ('DSTV', 'DSTV decoder, dish, signal, and subscription hardware issues.'),
    ('Door Locks', 'Door alignment, lock fitting, access, and key-related issues.'),
    ('Bathroom', 'Showers, sinks, toilets, fittings, and bathroom fixture problems.'),
    ('Roof', 'Roof leaks, ceiling seepage, and weather-related structural defects.'),
    ('Windows', 'Broken panes, handles, frames, and window sealing issues.'),
    ('Kitchen Equipment', 'Cookers, freezers, fridges, and kitchen appliance maintenance.'),
    ('Laundry Equipment', 'Washers, dryers, pressing equipment, and laundry utility issues.'),
    ('Security', 'CCTV, access control, alarms, and safety equipment concerns.'),
    ('General', 'General maintenance issues that do not fit a specific category.'),
]


def seed_default_maintenance_categories(apps, schema_editor):
    MaintenanceCategory = apps.get_model('tasks', 'MaintenanceCategory')
    for name, description in DEFAULT_MAINTENANCE_CATEGORIES:
        MaintenanceCategory.objects.update_or_create(
            name=name,
            defaults={
                'description': description,
                'is_active': True,
            },
        )


def unseed_default_maintenance_categories(apps, schema_editor):
    MaintenanceCategory = apps.get_model('tasks', 'MaintenanceCategory')
    MaintenanceCategory.objects.filter(
        name__in=[name for name, _description in DEFAULT_MAINTENANCE_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0008_maintenancecategory_maintenanceissue_and_more'),
    ]

    operations = [
        migrations.RunPython(
            seed_default_maintenance_categories,
            unseed_default_maintenance_categories,
        ),
    ]
