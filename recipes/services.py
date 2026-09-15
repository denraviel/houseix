from decimal import Decimal

from django.db import transaction

from inventory.models import InventoryTransaction
from inventory.services import InventoryBatchService


class RecipeProductionService:
    """
    Consumes the inventory required to produce `units_sold` units of a
    recipe-costed product's finished output, via FIFO, and returns the
    actual COGS plus a per-ingredient breakdown for auditability. This is
    the only place recipe-driven inventory consumption should happen, so it
    stays hooked into whatever single point already deducts Product stock
    on sale (avoiding double deduction).
    """

    @classmethod
    @transaction.atomic
    def consume_for_sale(cls, *, recipe, units_sold, user=None, sale=None, reference=''):
        if units_sold <= 0:
            raise ValueError('units_sold must be greater than zero.')

        portion_fraction = Decimal(units_sold) / recipe.yield_quantity
        total_cogs = Decimal('0')
        breakdown = []

        for ingredient in recipe.ingredients.filter(is_active=True).select_related('inventory_item'):
            required_qty = ingredient.effective_quantity * portion_fraction
            consumed = InventoryBatchService.consume(
                item=ingredient.inventory_item,
                quantity=required_qty,
                transaction_type=InventoryTransaction.TYPE_RECIPE_CONSUMPTION,
                user=user,
                recipe=recipe,
                sale=sale,
                reference=reference or f"Recipe: {recipe.product.name}",
                reason=f"{recipe.product.name} preparation" + (f" (Order #{sale.pk})" if sale else ''),
            )
            for batch, qty, unit_cost in consumed:
                cost = qty * unit_cost
                total_cogs += cost
                breakdown.append({
                    'inventory_item': ingredient.inventory_item.item_name,
                    'batch_id': batch.pk,
                    'quantity': str(qty),
                    'unit_cost': str(unit_cost),
                    'cost': str(cost),
                })

        # Extra costs (gas/packaging/etc.) are not inventory-tracked, so they
        # scale by the same portion fraction without touching stock batches.
        for extra in recipe.extra_costs.filter(is_active=True):
            extra_cost = (extra.amount / recipe.yield_quantity) * Decimal(units_sold)
            total_cogs += extra_cost
            breakdown.append({
                'inventory_item': extra.name,
                'batch_id': None,
                'quantity': None,
                'unit_cost': None,
                'cost': str(extra_cost.quantize(Decimal('0.01'))),
            })

        return total_cogs.quantize(Decimal('0.01')), breakdown
