from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import module_permission_required
from accounts.services import NavigationService
from products.models import Product

from .forms import RecipeExtraCostFormSet, RecipeForm, RecipeIngredientFormSet
from .models import Recipe


@login_required
@module_permission_required(NavigationService.MODULE_PRODUCTS)
def recipe_edit(request, product_pk):
    if request.user.role not in ['owner', 'admin', 'manager']:
        messages.error(request, 'You are not authorized to edit recipes.')
        return redirect('product_list')

    product = get_object_or_404(Product, pk=product_pk)
    recipe, _ = Recipe.objects.get_or_create(product=product)

    if request.method == 'POST':
        recipe_form = RecipeForm(request.POST, instance=recipe)
        ingredient_formset = RecipeIngredientFormSet(request.POST, instance=recipe, prefix='ingredients')
        extra_cost_formset = RecipeExtraCostFormSet(request.POST, instance=recipe, prefix='extras')
        if recipe_form.is_valid() and ingredient_formset.is_valid() and extra_cost_formset.is_valid():
            recipe_form.save()
            ingredient_formset.save()
            extra_cost_formset.save()
            if product.costing_method != Product.COSTING_METHOD_RECIPE:
                product.costing_method = Product.COSTING_METHOD_RECIPE
                product.save(update_fields=['costing_method'])
            messages.success(request, f"Recipe saved. Current cost per {recipe.yield_unit}: {recipe.calculate_cost_per_unit()}.")
            from accounts.models import AuditLog
            AuditLog.log(request.user, 'recipe_saved', f"Saved recipe for {product.name}")
            return redirect('recipe_edit', product_pk=product.pk)
    else:
        recipe_form = RecipeForm(instance=recipe)
        ingredient_formset = RecipeIngredientFormSet(instance=recipe, prefix='ingredients')
        extra_cost_formset = RecipeExtraCostFormSet(instance=recipe, prefix='extras')

    return render(request, 'recipes/recipe_edit.html', {
        'product': product,
        'recipe': recipe,
        'recipe_form': recipe_form,
        'ingredient_formset': ingredient_formset,
        'extra_cost_formset': extra_cost_formset,
        'breakdown': recipe.cost_breakdown() if recipe.pk else [],
        'batch_cost': recipe.calculate_batch_cost() if recipe.pk else 0,
        'cost_per_unit': recipe.calculate_cost_per_unit() if recipe.pk else 0,
    })


@login_required
@module_permission_required(NavigationService.MODULE_PRODUCTS)
def product_costing_detail(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    recipe = getattr(product, 'recipe', None)
    context = {
        'product': product,
        'recipe': recipe,
        'breakdown': recipe.cost_breakdown() if recipe else [],
        'batch_cost': recipe.calculate_batch_cost() if recipe else None,
    }
    return render(request, 'recipes/product_costing_detail.html', context)
