from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0013_alter_task_created_at_alter_task_updated_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inspectiontemplateitem',
            name='section',
            field=models.CharField(
                choices=[
                    ('bed_living', 'Bed & Living'),
                    ('bathroom', 'Bathroom'),
                    ('touchpoints', 'Touchpoints'),
                    ('floors_waste', 'Floors & Waste'),
                    ('amenities', 'Amenities'),
                    ('surfaces_equipment', 'Surfaces & Equipment'),
                    ('floors_grounds', 'Floors & Grounds'),
                    ('waste_hygiene', 'Waste & Hygiene'),
                    ('safety_compliance', 'Safety & Compliance'),
                    ('stock_supplies', 'Stock & Supplies'),
                ],
                max_length=50,
            ),
        ),
    ]
