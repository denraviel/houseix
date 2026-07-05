
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        # Add new fields
        migrations.AddField(
            model_name='inventoryitem',
            name='category',
            field=models.CharField(choices=[('Kitchen', 'Kitchen'), ('Bar', 'Bar'), ('Cleaning', 'Cleaning'), ('Room Supplies', 'Room Supplies'), ('Food Items', 'Food Items'), ('Others', 'Others')], default='Others', max_length=50),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='cost_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='low_stock_threshold',
            field=models.IntegerField(default=5),
        ),
        # Rename updated_at to last_updated
        migrations.RenameField(
            model_name='inventoryitem',
            old_name='updated_at',
            new_name='last_updated',
        ),
    ]
