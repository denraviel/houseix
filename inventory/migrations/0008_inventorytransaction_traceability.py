import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_seed_opening_stock_batches'),
        ('recipes', '0001_initial'),
        ('sales', '0008_backfill_sale_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorytransaction',
            name='recipe',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_transactions', to='recipes.recipe',
                help_text='The recipe/dish that caused this consumption, if any.',
            ),
        ),
        migrations.AddField(
            model_name='inventorytransaction',
            name='sale',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='inventory_transactions', to='sales.sale',
                help_text='The specific order/sale that caused this movement, if any.',
            ),
        ),
        migrations.AddField(
            model_name='inventorytransaction',
            name='previous_quantity',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=12, null=True,
                help_text="This item's total stock across all batches immediately before this transaction.",
            ),
        ),
        migrations.AddField(
            model_name='inventorytransaction',
            name='new_quantity',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=12, null=True,
                help_text="This item's total stock across all batches immediately after this transaction.",
            ),
        ),
    ]
