from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0005_alter_sale_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='actual_cogs',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True,
                help_text='Actual cost of goods sold at the time of this sale. Captured once and never recalculated, so later inventory price changes cannot alter historical cost.',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='cogs_breakdown',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Which inventory batches/quantities/costs made up actual_cogs, for auditability.',
            ),
        ),
    ]
