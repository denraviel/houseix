from django import forms
from .models import Sale
from products.models import Product
from stays.models import GuestStay


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['stay', 'product', 'quantity', 'payment_method']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stay'].queryset = GuestStay.objects.select_related('customer', 'room').order_by('-created_at')
        self.fields['stay'].required = False
        self.fields['stay'].help_text = 'Select a guest stay to link this sale to the guest record.'
        # Only show products available for sale
        self.fields['product'].queryset = Product.objects.filter(
            quantity_in_stock__gt=0,
            is_available=True
        )
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        product = self.cleaned_data.get('product')
        
        if product and quantity > product.quantity_in_stock:
            raise forms.ValidationError("Not enough stock available")
        
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        stay = cleaned_data.get('stay')
        if stay and stay.is_closed and not stay.check_out_date:
            self.add_error('stay', 'This closed stay has no check-out date recorded yet.')
        return cleaned_data
