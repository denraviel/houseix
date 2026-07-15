from django import forms

from stays.models import GuestStay

from .models import Sale
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
        
        if product and quantity > product.quantity_in_stock:
            raise forms.ValidationError("Not enough stock available")
        
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        stay = cleaned_data.get('stay')
        if stay and stay.is_closed:
            self.add_error('stay', 'Sales cannot be recorded for a guest who has already checked out or whose stay is closed.')
        return cleaned_data
