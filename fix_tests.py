import io

path = "sales/tests.py"
with io.open(path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
(
"""    def test_sale_of_recipe_product_captures_actual_cogs(self):
        sale = Sale(
            product=self.product, quantity=2, payment_method='cash', recorded_by=self.staff,
        )
        sale.save()
        sale.refresh_from_db()
        self.assertIsNotNone(sale.actual_cogs)
        self.assertGreater(sale.actual_cogs, 0)
        self.assertIsNotNone(sale.cogs_breakdown)""",
"""    def test_sale_of_recipe_product_captures_actual_cogs(self):
        from sales.services import SaleWorkflowService

        sale = Sale(
            product=self.product, quantity=2, payment_method='cash', recorded_by=self.staff,
        )
        sale.save()
        SaleWorkflowService.mark_prepared(sale=sale, user=self.staff)
        sale.refresh_from_db()
        self.assertIsNotNone(sale.actual_cogs)
        self.assertGreater(sale.actual_cogs, 0)
        self.assertIsNotNone(sale.cogs_breakdown)"""
),
(
"""    def test_sale_blocked_when_insufficient_stock(self):
        from inventory.services import InsufficientStockError

        # Recipe needs 5kg per 10 portions -> selling 50 portions needs 25kg, only 10kg exists.
        sale = Sale(product=self.product, quantity=50, payment_method='cash', recorded_by=self.staff)
        with self.assertRaises(InsufficientStockError):
            sale.save()

        self.assertEqual(Sale.objects.filter(product=self.product).count(), 0)  # rolled back, nothing persisted
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('10'))  # untouched""",
"""    def test_sale_blocked_when_insufficient_stock(self):
        from inventory.services import InsufficientStockError
        from sales.services import SaleWorkflowService

        # Recipe needs 5kg per 10 portions -> selling 50 portions needs 25kg, only 10kg exists.
        # Creating the order itself succeeds (no consumption yet) - it's marking it
        # prepared that must fail, since that's when ingredients are actually needed.
        sale = Sale(product=self.product, quantity=50, payment_method='cash', recorded_by=self.staff)
        sale.save()

        with self.assertRaises(InsufficientStockError):
            SaleWorkflowService.mark_prepared(sale=sale, user=self.staff)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_CREATED)  # never advanced past created
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.total_batch_quantity, Decimal('10'))  # untouched"""
),
(
'''    def test_five_separate_orders_each_consume_their_own_portion(self):
        """5 guests order 1 Jollof Rice each, separately - not one batch of 5."""
        for _ in range(5):
            sale = Sale(product=self.jollof, quantity=1, payment_method='cash', recorded_by=self.owner)
            sale.save()

        self.assertEqual(Sale.objects.filter(product=self.jollof).count(), 5)
        # 5 orders x 0.2kg = 1kg consumed total, each captured with its own actual_cogs.
        remaining = self.rice.batches.first().quantity_remaining
        self.assertEqual(remaining, Decimal('9'))
        for sale in Sale.objects.filter(product=self.jollof):
            self.assertIsNotNone(sale.actual_cogs)
            self.assertEqual(sale.actual_cogs, Decimal('450.00'))  # 0.2kg * 2000/kg + 50 gas''',
'''    def test_five_separate_orders_each_consume_their_own_portion(self):
        """5 guests order 1 Jollof Rice each, separately - not one batch of 5."""
        from sales.services import SaleWorkflowService

        for _ in range(5):
            sale = Sale(product=self.jollof, quantity=1, payment_method='cash', recorded_by=self.owner)
            sale.save()
            SaleWorkflowService.mark_prepared(sale=sale, user=self.owner)

        self.assertEqual(Sale.objects.filter(product=self.jollof).count(), 5)
        # 5 orders x 0.2kg = 1kg consumed total, each captured with its own actual_cogs.
        remaining = self.rice.batches.first().quantity_remaining
        self.assertEqual(remaining, Decimal('9'))
        for sale in Sale.objects.filter(product=self.jollof):
            self.assertIsNotNone(sale.actual_cogs)
            self.assertEqual(sale.actual_cogs, Decimal('450.00'))  # 0.2kg * 2000/kg + 50 gas'''
),
]

made = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        made += 1
    else:
        print("WARNING: a pattern was not found - one replacement was skipped")

with io.open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("Applied " + str(made) + " of 3 replacements.")