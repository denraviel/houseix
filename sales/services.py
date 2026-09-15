from products.models import Product


class SalesAccessService:
    BAR_POSITION_CODES = {'barman', 'bartender'}
    BAR_PRODUCT_CATEGORIES = {'Bar'}
    PRIVILEGED_ROLES = {'owner', 'admin', 'manager'}

    @classmethod
    def user_position_codes(cls, user):
        if not getattr(user, 'is_authenticated', False):
            return set()
        return set(user.positions.filter(is_active=True).values_list('code', flat=True))

    @classmethod
    def is_bar_sales_user(cls, user):
        return bool(cls.user_position_codes(user) & cls.BAR_POSITION_CODES)

    @staticmethod
    def base_product_queryset():
        from django.db.models import Q
        # Manual-costed products are genuinely stocked (must have quantity_in_stock),
        # but recipe-costed dishes are made to order from raw inventory - there is
        # no finished-dish count, so they stay listed as long as they're toggled on.
        return Product.objects.filter(
            Q(costing_method=Product.COSTING_METHOD_MANUAL, quantity_in_stock__gt=0)
            | Q(costing_method=Product.COSTING_METHOD_RECIPE),
            is_available=True,
        ).order_by('category', 'name')

    @classmethod
    def available_products_for_user(cls, user):
        queryset = cls.base_product_queryset()
        if not getattr(user, 'is_authenticated', False):
            return queryset.none()
        if getattr(user, 'role', None) in cls.PRIVILEGED_ROLES:
            return queryset
        if cls.is_bar_sales_user(user):
            return queryset.filter(category__in=cls.BAR_PRODUCT_CATEGORIES)
        return queryset

    @classmethod
    def sales_queryset_for_user(cls, user):
        from .models import Sale

        queryset = Sale.objects.select_related(
            'product',
            'recorded_by',
            'customer',
            'room',
            'stay',
        ).order_by('-created_at')
        if not getattr(user, 'is_authenticated', False):
            return queryset.none()
        if getattr(user, 'role', None) in cls.PRIVILEGED_ROLES:
            return queryset
        if cls.is_bar_sales_user(user):
            return queryset.filter(recorded_by=user, product__category__in=cls.BAR_PRODUCT_CATEGORIES)
        return queryset.filter(recorded_by=user)


class SaleWorkflowService:
    """
    Owns the order lifecycle transitions. Inventory consumption for
    recipe-costed dishes happens ONLY here, at the "prepared/served" step -
    never at order creation - so a cancelled order that never reached the
    kitchen consumes nothing.
    """

    @classmethod
    def mark_prepared(cls, *, sale, user):
        from django.db import transaction
        from django.utils import timezone

        if sale.status == sale.STATUS_CANCELLED:
            raise ValueError('This order was cancelled and cannot be marked prepared.')
        if sale.status not in sale.PRE_CONSUMPTION_STATUSES:
            raise ValueError(f"This order is already '{sale.get_status_display()}' and cannot be prepared again.")

        product = sale.product
        with transaction.atomic():
            if product.costing_method == product.COSTING_METHOD_RECIPE:
                recipe = getattr(product, 'recipe', None)
                if recipe is not None and recipe.is_active and recipe.ingredients.filter(is_active=True).exists():
                    from recipes.services import RecipeProductionService
                    actual_cogs, breakdown = RecipeProductionService.consume_for_sale(
                        recipe=recipe,
                        units_sold=sale.quantity,
                        user=user,
                        sale=sale,
                    )
                    sale.actual_cogs = actual_cogs
                    sale.cogs_breakdown = breakdown
            sale.status = sale.STATUS_PREPARED
            sale.prepared_at = timezone.now()
            sale.prepared_by = user
            sale.save(update_fields=['status', 'prepared_at', 'prepared_by', 'actual_cogs', 'cogs_breakdown'])
        return sale

    @classmethod
    def cancel(cls, *, sale, user, reason=''):
        from django.utils import timezone

        if sale.status not in sale.PRE_CONSUMPTION_STATUSES:
            raise ValueError(
                f"This order is already '{sale.get_status_display()}' - ingredients/stock may already be "
                f"consumed, so it can no longer be cancelled here."
            )
        sale.status = sale.STATUS_CANCELLED
        sale.cancelled_at = timezone.now()
        sale.cancelled_by = user
        sale.cancellation_reason = reason
        sale.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])
        return sale
