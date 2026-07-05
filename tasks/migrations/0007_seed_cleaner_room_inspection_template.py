from django.db import migrations


TEMPLATE_NAME = 'Cleaner Room Inspection'
TEMPLATE_ROLE = 'Cleaner'
TEMPLATE_DESCRIPTION = 'Default reusable room inspection checklist for cleaning audits.'

ITEMS = [
    ('bed_living', 'Linens crisp, wrinkle-free, no hairs', 'critical', 10, 1),
    ('bathroom', 'Toilet completely sanitized (rim, base, behind)', 'critical', 10, 2),
    ('floors_waste', 'Bins emptied, washed, and freshly lined', 'critical', 10, 3),
    ('bed_living', 'Under bed clear of dust/trash', 'standard', 5, 4),
    ('bed_living', 'TV screen streak-free', 'standard', 5, 5),
    ('bed_living', 'Remote sanitized', 'standard', 5, 6),
    ('bathroom', 'Fixtures free of water spots', 'standard', 5, 7),
    ('bathroom', 'Tiles, grout and corners mold free', 'standard', 5, 8),
    ('bathroom', 'Mirrors streak free', 'standard', 5, 9),
    ('touchpoints', 'Door handles sanitized', 'standard', 5, 10),
    ('touchpoints', 'Light switches sanitized', 'standard', 5, 11),
    ('floors_waste', 'Carpets vacuumed', 'standard', 5, 12),
    ('floors_waste', 'Floors properly mopped', 'standard', 5, 13),
    ('amenities', 'Minibar organized', 'standard', 5, 14),
    ('amenities', 'Kettle clean', 'standard', 5, 15),
    ('amenities', 'Tea restocked', 'standard', 5, 16),
    ('amenities', 'Coffee restocked', 'standard', 5, 17),
    ('amenities', 'Toiletries restocked', 'standard', 5, 18),
    ('bed_living', 'Wardrobe tops dusted', 'detail', 2, 19),
    ('touchpoints', 'Wardrobe shelves wiped', 'detail', 2, 20),
    ('touchpoints', 'Drawers wiped', 'detail', 2, 21),
    ('touchpoints', 'Window sills dusted', 'detail', 2, 22),
    ('touchpoints', 'Glass clean', 'detail', 2, 23),
    ('floors_waste', 'Floor edges clean', 'detail', 2, 24),
    ('floors_waste', 'Wall corners clean', 'detail', 2, 25),
    ('amenities', 'Menus aligned', 'detail', 2, 26),
    ('amenities', 'Stationery aligned', 'detail', 2, 27),
]


def seed_cleaner_template(apps, schema_editor):
    InspectionTemplate = apps.get_model('tasks', 'InspectionTemplate')
    InspectionTemplateItem = apps.get_model('tasks', 'InspectionTemplateItem')

    template, _ = InspectionTemplate.objects.get_or_create(
        name=TEMPLATE_NAME,
        defaults={
            'role': TEMPLATE_ROLE,
            'description': TEMPLATE_DESCRIPTION,
            'is_active': True,
        },
    )
    if template.role != TEMPLATE_ROLE or template.description != TEMPLATE_DESCRIPTION or not template.is_active:
        template.role = TEMPLATE_ROLE
        template.description = TEMPLATE_DESCRIPTION
        template.is_active = True
        template.save(update_fields=['role', 'description', 'is_active', 'updated_at'])

    existing = set(template.items.values_list('description', flat=True))
    for section, description, severity, deduction_points, display_order in ITEMS:
        if description in existing:
            continue
        InspectionTemplateItem.objects.create(
            template=template,
            section=section,
            description=description,
            severity=severity,
            deduction_points=deduction_points,
            display_order=display_order,
        )


def unseed_cleaner_template(apps, schema_editor):
    InspectionTemplate = apps.get_model('tasks', 'InspectionTemplate')
    InspectionTemplate.objects.filter(name=TEMPLATE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0006_task_previous_task_task_requires_inspection_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_cleaner_template, unseed_cleaner_template),
    ]
