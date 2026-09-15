import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0005_alter_inventoryitem_id_alter_stockmovement_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_received', models.DecimalField(decimal_places=3, max_digits=12)),
                ('quantity_remaining', models.DecimalField(decimal_places=3, max_digits=12)),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=12)),
                ('supplier', models.CharField(blank=True, max_length=255)),
                ('purchased_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_opening_balance', models.BooleanField(default=False, help_text='True for the batch auto-created from pre-existing stock when this system was introduced.')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='inventory.inventoryitem')),
                ('received_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_batches_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['purchased_at', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='stockbatch',
            constraint=models.CheckConstraint(condition=models.Q(('quantity_received__gte', 0)), name='stockbatch_quantity_received_nonneg'),
        ),
        migrations.AddConstraint(
            model_name='stockbatch',
            constraint=models.CheckConstraint(condition=models.Q(('quantity_remaining__gte', 0)), name='stockbatch_quantity_remaining_nonneg'),
        ),
        migrations.AddConstraint(
            model_name='stockbatch',
            constraint=models.CheckConstraint(condition=models.Q(('unit_cost__gte', 0)), name='stockbatch_unit_cost_nonneg'),
        ),
        migrations.CreateModel(
            name='InventoryTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('purchase', 'Purchase'), ('sale_consumption', 'Sale Consumption'), ('recipe_consumption', 'Recipe Consumption'), ('wastage', 'Wastage'), ('adjustment', 'Adjustment'), ('transfer', 'Transfer'), ('manual_take', 'Manual Stock Take')], max_length=30)),
                ('quantity', models.DecimalField(decimal_places=3, help_text='Positive for additions, negative for consumption/wastage.', max_digits=12)),
                ('unit_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('total_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('reference', models.CharField(blank=True, help_text='e.g. Sale #123, Recipe: Fried Rice', max_length=255)),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='inventory.stockbatch')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='inventory.inventoryitem')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
