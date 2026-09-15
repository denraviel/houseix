from django import forms

from stays.models import GuestStay

from .models import Order, Sale
from .services import SalesAccessService


class SaleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['stay'].queryset = GuestStay.objects.select_related('customer', 'room').filter(
            status__in=GuestStay.ACTIVE_STATUSES
        ).order_by('-created_at')
        self.fields['stay'].required = False
        self.fields['stay'].help_text = 'Select an active guest stay to link this sale to the guest record.'
        self.fields['product'].queryset = SalesAccessService.available_products_for_user(self.user)
        if SalesAccessService.is_bar_sales_user(self.user):
            self.fields['product'].help_text = 'Only products in the Bar category are available for your position.'
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'

    class Meta:
        model = Sale
        fields = ['stay', 'product', 'quantity', 'payment_method']
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        product = self.cleaned_data.get('product')
        
        # Recipe-costed dishes are made fresh per order from raw inventory -
        # real availability is enforced when ingredients are actually
        # consumed (FIFO, raises a clear error if insufficient), not by a
        # finished-dish counter that doesn't exist for made-to-order food.
        if product and product.costing_method == product.COSTING_METHOD_MANUAL:
            if quantity > product.quantity_in_stock:
                raise forms.ValidationError("Not enough stock available")
        
        return quantity

   
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        if product and quantity and product.costing_method == product.COSTING_METHOD_RECIPE:
            recipe = getattr(product, 'recipe', None)
            if recipe is not None and recipe.is_active and recipe.ingredients.filter(is_active=True).exists():
                shortfalls = recipe.get_insufficient_ingredients(units=quantity)
                if shortfalls:
                    details = ', '.join(
                        f"{s['inventory_item'].item_name} (need {s['required']}, have {s['available']} {s['inventory_item'].unit_type})"
                        for s in shortfalls
                    )
                    raise forms.ValidationError(f"Cannot take this order - insufficient ingredients: {details}")
        return cleaned_data


class OrderForm(forms.ModelForm):
    """Ticket-level details, entered once for the whole order."""

    class Meta:
        model = Order
        fields = ['stay', 'payment_method', 'notes']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['stay'].queryset = GuestStay.objects.select_related('customer', 'room').filter(
            status__in=GuestStay.ACTIVE_STATUSES
        ).order_by('-created_at')
        self.fields['stay'].required = False
        self.fields['stay'].help_text = 'Select an active guest stay to link this order to the guest record.'
        self.fields['notes'].required = False
        self.fields['notes'].widget = forms.Textarea(attrs={'rows': 2})
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


class OrderItemForm(forms.ModelForm):
    """One product line on an order."""

    class Meta:
        model = Sale
        fields = ['product', 'quantity']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = SalesAccessService.available_products_for_user(self.user)
        self.fields['product'].required = False
        self.fields['quantity'].required = False
        self.fields['product'].widget.attrs['class'] = 'form-select form-select-sm'
        self.fields['quantity'].widget.attrs['class'] = 'form-control form-control-sm'

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')

        if not product and not quantity:
            return cleaned_data  # blank row, ignored
        if product and not quantity:
            raise forms.ValidationError('Enter a quantity for this item.')
        if quantity and not product:
            raise forms.ValidationError('Select a product for this item.')
        if quantity < 1:
            raise forms.ValidationError('Quantity must be at least 1.')

        if product.costing_method == product.COSTING_METHOD_MANUAL:
            if quantity > product.quantity_in_stock:
                raise forms.ValidationError(
                    f"Not enough {product.name} in stock (have {product.quantity_in_stock})."
                )
        else:
            recipe = getattr(product, 'recipe', None)
            if recipe is not None and recipe.is_active and recipe.ingredients.filter(is_active=True).exists():
                shortfalls = recipe.get_insufficient_ingredients(units=quantity)
                if shortfalls:
                    details = ', '.join(
                        f"{s['inventory_item'].item_name} (need {s['required']}, "
                        f"have {s['available']} {s['inventory_item'].unit_type})"
                        for s in shortfalls
                    )
                    # Flagged on the line, so the rest of the order can still
                    # go through - the kitchen just can't make this one dish.
                    raise forms.ValidationError(f"Insufficient ingredients: {details}")
        return cleaned_data


OrderItemFormSet = forms.modelformset_factory(
    Sale, form=OrderItemForm, extra=3, can_delete=False,
)
