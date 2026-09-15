from django import forms
from decimal import Decimal
from .models import InventoryItem, StockMovement


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['item_name', 'category', 'quantity', 'unit_type', 'cost_price', 'low_stock_threshold']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
    
    def clean(self):
        cleaned_data = super().clean()
        item_name = cleaned_data.get('item_name')
        category = cleaned_data.get('category')
        
        if InventoryItem.objects.filter(item_name=item_name, category=category).exists():
            raise forms.ValidationError('Item already exists. Would you like to add stock to the existing item instead?')
        
        return cleaned_data


class AddStockForm(forms.Form):
    quantity_to_add = forms.DecimalField(min_value=Decimal('0.001'), max_digits=12, decimal_places=3, label='Quantity Received')
    unit_cost = forms.DecimalField(min_value=Decimal('0'), max_digits=12, decimal_places=2, label='Purchase Cost (per unit)')
    supplier = forms.CharField(max_length=255, required=False, label='Supplier (optional)')
    purchased_at = forms.DateTimeField(
        required=False,
        label='Purchase Date',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['item', 'quantity_taken']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.widgets.Input):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
