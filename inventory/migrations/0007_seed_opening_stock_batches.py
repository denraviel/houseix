from django.db import migrations
from django.utils import timezone


def create_opening_batches(apps, schema_editor):
    InventoryItem = apps.get_model('inventory', 'InventoryItem')
    StockBatch = apps.get_model('inventory', 'StockBatch')
    InventoryTransaction = apps.get_model('inventory', 'InventoryTransaction')

    now = timezone.now()
    for item in InventoryItem.objects.all():
        if item.quantity and item.quantity > 0:
            batch = StockBatch.objects.create(
                item=item,
                quantity_received=item.quantity,
                quantity_remaining=item.quantity,
                unit_cost=item.cost_price or 0,
                purchased_at=item.created_at or now,
                is_opening_balance=True,
            )
            InventoryTransaction.objects.create(
                item=item,
                batch=batch,
                transaction_type='purchase',
                quantity=item.quantity,
                unit_cost=item.cost_price or 0,
                total_cost=(item.cost_price or 0) * item.quantity,
                reference='Opening balance (batch system introduced)',
            )


def remove_opening_batches(apps, schema_editor):
    StockBatch = apps.get_model('inventory', 'StockBatch')
    StockBatch.objects.filter(is_opening_balance=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_stockbatch_inventorytransaction'),
    ]

    operations = [
        migrations.RunPython(create_opening_batches, remove_opening_batches),
    ]
