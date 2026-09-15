from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import InventoryItem, InventoryTransaction, StockBatch


class InsufficientStockError(Exception):
    """Raised when a consumption request exceeds available batch stock."""

    def __init__(self, item, requested, available):
        self.item = item
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for {item.item_name}: requested {requested}, available {available}."
        )


class InventoryBatchService:
    """
    Owns all batch creation and FIFO consumption logic. Nothing outside this
    service should mutate StockBatch.quantity_remaining directly, so the
    ledger (InventoryTransaction) and the batches always agree.
    """

    @classmethod
    @transaction.atomic
    def add_stock(cls, *, item, quantity, unit_cost, user, supplier='', purchased_at=None, reference=''):
        """Create a new, immutable stock batch. Never modifies existing batches."""
        if quantity <= 0:
            raise ValueError('Quantity received must be greater than zero.')
        if unit_cost < 0:
            raise ValueError('Unit cost cannot be negative.')

        batch = StockBatch.objects.create(
            item=item,
            quantity_received=quantity,
            quantity_remaining=quantity,
            unit_cost=unit_cost,
            supplier=supplier,
            purchased_at=purchased_at or timezone.now(),
            received_by=user,
        )
        previous_quantity = item.total_batch_quantity - quantity  # before this batch existed
        InventoryTransaction.objects.create(
            item=item,
            batch=batch,
            transaction_type=InventoryTransaction.TYPE_PURCHASE,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            reference=reference,
            performed_by=user,
            previous_quantity=previous_quantity,
            new_quantity=previous_quantity + quantity,
        )
        # Keep the legacy flat fields in sync for anything not yet batch-aware
        # (e.g. low-stock checks, display fallbacks).
        InventoryItem.objects.filter(pk=item.pk).update(
            quantity=models_f_quantity(item),
            cost_price=unit_cost,
        )
        return batch

    @classmethod
    @transaction.atomic
    def consume(cls, *, item, quantity, transaction_type, user=None, recipe=None, sale=None, reference='', reason=''):
        """
        Consume `quantity` of `item` via FIFO across its stock batches.
        Returns a list of (batch, quantity_consumed, unit_cost) tuples
        describing exactly what was consumed, for COGS purposes.
        Raises InsufficientStockError if there isn't enough stock; nothing
        is mutated in that case (the whole operation rolls back).
        Every resulting InventoryTransaction records who did it (user),
        why (reason), which dish (recipe) and which order (sale) caused it,
        plus a before/after snapshot of the item's total stock - so no
        deduction is ever anonymous.
        """
        if quantity <= 0:
            raise ValueError('Consumption quantity must be greater than zero.')

        batches = list(
            StockBatch.objects.select_for_update()
            .filter(item=item, quantity_remaining__gt=0)
            .order_by('purchased_at', 'id')
        )
        available = sum((b.quantity_remaining for b in batches), Decimal('0'))
        if available < quantity:
            raise InsufficientStockError(item=item, requested=quantity, available=available)

        remaining_to_consume = quantity
        consumed = []
        running_total = item.total_batch_quantity
        for batch in batches:
            if remaining_to_consume <= 0:
                break
            take = min(batch.quantity_remaining, remaining_to_consume)
            batch.quantity_remaining -= take
            batch.save(update_fields=['quantity_remaining'])
            previous_quantity = running_total
            running_total -= take
            InventoryTransaction.objects.create(
                item=item,
                batch=batch,
                transaction_type=transaction_type,
                quantity=-take,
                unit_cost=batch.unit_cost,
                total_cost=take * batch.unit_cost,
                reference=reference,
                reason=reason,
                recipe=recipe,
                sale=sale,
                performed_by=user,
                previous_quantity=previous_quantity,
                new_quantity=running_total,
            )
            consumed.append((batch, take, batch.unit_cost))
            remaining_to_consume -= take

        InventoryItem.objects.filter(pk=item.pk).update(quantity=models_f_quantity(item))
        return consumed

    @classmethod
    @transaction.atomic
    def record_wastage(cls, *, item, quantity, user, reason=''):
        return cls.consume(
            item=item,
            quantity=quantity,
            transaction_type=InventoryTransaction.TYPE_WASTAGE,
            user=user,
            reason=reason,
            reference='Wastage',
        )


def models_f_quantity(item):
    """
    Recompute the legacy flat InventoryItem.quantity field from batch data,
    rounded to an int since the legacy field is an IntegerField. Kept as a
    compatibility bridge for any code still reading item.quantity directly.
    """
    total = item.total_batch_quantity
    return int(total)
