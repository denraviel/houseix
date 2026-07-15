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
        return Product.objects.filter(
            quantity_in_stock__gt=0,
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
