from django.db import migrations


def backfill_sale_status(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    # Manual-costed sales always completed instantly - mark them completed.
    Sale.objects.filter(product__costing_method='manual').update(status='completed')
    # Recipe-costed sales that already have actual_cogs were already
    # consumed under the old "consume at creation" model - mark them
    # 'prepared' so mark_prepared() can never be called on them again
    # and double-consume the same ingredients.
    Sale.objects.filter(product__costing_method='recipe', actual_cogs__isnull=False).update(status='prepared')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0007_sale_order_lifecycle'),
        ('products', '0005_product_costing_method'),
    ]

    operations = [
        migrations.RunPython(backfill_sale_status, noop_reverse),
    ]
