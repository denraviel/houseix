from django.db import migrations


TEMPLATES = [
    {
        'name': 'Kitchen & Public Area Cleaning',
        'role': 'Cleaner',
        'description': 'Reusable checklist for kitchen and public/common area cleaning audits.',
        'position_codes': ['cleaner', 'kitchen_assistant'],
        'items': [
            ('surfaces_equipment', 'Countertops sanitized, free of food residue', 'critical', 10, 1),
            ('surfaces_equipment', 'Cooking equipment surfaces degreased (stove, oven exterior)', 'critical', 10, 2),
            ('waste_hygiene', 'Floor drains and grease traps clear of buildup', 'critical', 10, 3),
            ('surfaces_equipment', 'Sink and basin scrubbed, free of stains', 'standard', 5, 4),
            ('floors_grounds', 'Kitchen floor swept and mopped', 'standard', 5, 5),
            ('waste_hygiene', 'Trash bins emptied and relined', 'standard', 5, 6),
            ('floors_grounds', 'Public area floors swept and mopped', 'standard', 5, 7),
            ('surfaces_equipment', 'Windows and glass doors in public areas wiped', 'standard', 5, 8),
            ('surfaces_equipment', 'Dining/public furniture wiped down and arranged', 'standard', 5, 9),
            ('surfaces_equipment', 'Refrigerator exterior wiped clean', 'standard', 5, 10),
            ('surfaces_equipment', 'Extractor hood and vents free of grease buildup', 'standard', 5, 11),
            ('surfaces_equipment', 'Shelves and storage racks dusted', 'detail', 2, 12),
            ('surfaces_equipment', 'Light fixtures and ceiling fans dust-free', 'detail', 2, 13),
            ('surfaces_equipment', 'Wall tiles behind cooking area free of splashes', 'detail', 2, 14),
        ],
    },
    {
        'name': 'Bar Area Cleaning',
        'role': 'Bar Staff',
        'description': 'Reusable checklist for bar area cleaning and hygiene audits.',
        'position_codes': ['barman', 'bartender', 'bar_supervisor'],
        'items': [
            ('surfaces_equipment', 'Bar counter and taps sanitized, no residue', 'critical', 10, 1),
            ('waste_hygiene', 'Glassware washed streak-free and stored properly', 'critical', 10, 2),
            ('waste_hygiene', 'Ice bin cleaned and free of debris', 'critical', 10, 3),
            ('floors_grounds', 'Bar floor swept and mopped, no spills', 'standard', 5, 4),
            ('surfaces_equipment', 'Bottles and shelves dusted and organized', 'standard', 5, 5),
            ('waste_hygiene', 'Sink area cleaned and properly drained', 'standard', 5, 6),
            ('waste_hygiene', 'Trash and recycling bins emptied', 'standard', 5, 7),
            ('surfaces_equipment', 'Bar stools and seating wiped down', 'standard', 5, 8),
            ('surfaces_equipment', 'Refrigerator/cooler interior wiped and organized', 'standard', 5, 9),
            ('stock_supplies', 'Coasters and napkin holders restocked and tidy', 'detail', 2, 10),
            ('surfaces_equipment', 'Menu boards/displays clean and straight', 'detail', 2, 11),
            ('surfaces_equipment', 'Light fixtures above bar dust-free', 'detail', 2, 12),
        ],
    },
    {
        'name': 'Compound Cleaning',
        'role': 'Security',
        'description': 'Reusable checklist for compound and exterior cleaning audits.',
        'position_codes': ['security_officer', 'security_supervisor'],
        'items': [
            ('floors_grounds', 'Main entrance and walkway swept clear of debris', 'critical', 10, 1),
            ('safety_compliance', 'Parking area free of litter and hazards', 'critical', 10, 2),
            ('floors_grounds', 'Compound perimeter swept (inside fence line)', 'standard', 5, 3),
            ('floors_grounds', 'Outside compound frontage swept', 'standard', 5, 4),
            ('waste_hygiene', 'Outdoor dustbins/waste points emptied', 'standard', 5, 5),
            ('safety_compliance', 'Drainage channels clear of debris', 'standard', 5, 6),
            ('surfaces_equipment', 'Signage and gate area wiped clean', 'standard', 5, 7),
            ('surfaces_equipment', 'Outdoor benches/seating dusted', 'detail', 2, 8),
            ('floors_grounds', 'Plant beds/landscaping edges tidy', 'detail', 2, 9),
            ('surfaces_equipment', 'Security post area organized', 'detail', 2, 10),
        ],
    },
]


def seed_templates(apps, schema_editor):
    InspectionTemplate = apps.get_model('tasks', 'InspectionTemplate')
    InspectionTemplateItem = apps.get_model('tasks', 'InspectionTemplateItem')
    JobPosition = apps.get_model('accounts', 'JobPosition')

    for spec in TEMPLATES:
        template, _ = InspectionTemplate.objects.get_or_create(
            name=spec['name'],
            defaults={
                'role': spec['role'],
                'description': spec['description'],
                'is_active': True,
            },
        )
        if template.role != spec['role'] or template.description != spec['description'] or not template.is_active:
            template.role = spec['role']
            template.description = spec['description']
            template.is_active = True
            template.save(update_fields=['role', 'description', 'is_active', 'updated_at'])

        position_ids = list(
            JobPosition.objects.filter(code__in=spec['position_codes']).values_list('pk', flat=True)
        )
        template.applicable_positions.set(position_ids)

        existing = set(template.items.values_list('description', flat=True))
        for section, description, severity, deduction_points, display_order in spec['items']:
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


def unseed_templates(apps, schema_editor):
    InspectionTemplate = apps.get_model('tasks', 'InspectionTemplate')
    InspectionTemplate.objects.filter(name__in=[spec['name'] for spec in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0014_alter_inspectiontemplateitem_section_choices'),
        ('accounts', '0017_seed_position_authority_graph'),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
