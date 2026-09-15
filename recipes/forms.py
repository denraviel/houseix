from django import forms
from django.forms import inlineformset_factory

from .models import Recipe, RecipeIngredient, RecipeExtraCost


class BootstrapFormMixin:
    def _apply_bootstrap(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.widgets.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.widgets.Select):
                field.widget.attrs['class'] = 'form-select form-select-sm'
            else:
                field.widget.attrs['class'] = 'form-control form-control-sm'


class RecipeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ['yield_quantity', 'yield_unit', 'notes', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class RecipeIngredientForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ['inventory_item', 'quantity', 'unit', 'waste_percentage', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class RecipeExtraCostForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RecipeExtraCost
        fields = ['name', 'amount', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


RecipeIngredientFormSet = inlineformset_factory(
    Recipe, RecipeIngredient, form=RecipeIngredientForm, extra=1, can_delete=True,
)

RecipeExtraCostFormSet = inlineformset_factory(
    Recipe, RecipeExtraCost, form=RecipeExtraCostForm, extra=1, can_delete=True,
)
