import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '0004_alter_product_id'),
        ('inventory', '0007_seed_opening_stock_batches'),
    ]

    operations = [
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('yield_quantity', models.DecimalField(decimal_places=3, default=Decimal('1'), max_digits=10)),
                ('yield_unit', models.CharField(default='portion', max_length=50)),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recipe', to='products.product')),
            ],
        ),
        migrations.AddConstraint(
            model_name='recipe',
            constraint=models.CheckConstraint(condition=models.Q(('yield_quantity__gt', 0)), name='recipe_yield_gt_zero'),
        ),
        migrations.CreateModel(
            name='RecipeIngredient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=10)),
                ('unit', models.CharField(help_text="Must be compatible with the inventory item's unit_type.", max_length=50)),
                ('waste_percentage', models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Optional. Extra percentage consumed to account for prep waste, e.g. 5.00 for 5%.', max_digits=5)),
                ('is_active', models.BooleanField(default=True)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recipe_uses', to='inventory.inventoryitem')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingredients', to='recipes.recipe')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='recipeingredient',
            constraint=models.CheckConstraint(condition=models.Q(('quantity__gt', 0)), name='recipeingredient_quantity_gt_zero'),
        ),
        migrations.CreateModel(
            name='RecipeExtraCost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='e.g. "Cooking Gas", "Takeaway Packaging"', max_length=100)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_costs', to='recipes.recipe')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='recipeextracost',
            constraint=models.CheckConstraint(condition=models.Q(('amount__gte', 0)), name='recipeextracost_amount_nonneg'),
        ),
    ]
