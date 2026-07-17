from django import forms
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
    quantity_to_add = forms.IntegerField(min_value=1, label='Quantity Received')
    
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