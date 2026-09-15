from django.urls import path
from . import views

urlpatterns = [
    path('product/<int:product_pk>/recipe/', views.recipe_edit, name='recipe_edit'),
    path('product/<int:product_pk>/costing/', views.product_costing_detail, name='product_costing_detail'),
]
