from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_alter_product_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='costing_method',
            field=models.CharField(choices=[('manual', 'Manual'), ('recipe', 'Recipe / Inventory')], default='manual', max_length=10),
        ),
        migrations.AlterField(
            model_name='product',
            name='cost_price',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                help_text='Manual cost. Used directly when costing_method is Manual, and as a fallback if a Recipe product has no recipe configured yet.',
            ),
        ),
    ]
