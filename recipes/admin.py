from django.contrib import admin
from .models import Recipe, RecipeIngredient, RecipeExtraCost


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1


class RecipeExtraCostInline(admin.TabularInline):
    model = RecipeExtraCost
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('product', 'yield_quantity', 'yield_unit', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('product__name',)
    inlines = [RecipeIngredientInline, RecipeExtraCostInline]
