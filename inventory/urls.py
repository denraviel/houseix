from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('item/create/', views.inventory_item_create, name='inventory_item_create'),
    path('item/<int:pk>/edit/', views.inventory_item_edit, name='inventory_item_edit'),
    path('item/<int:pk>/add-stock/', views.add_stock, name='add_stock'),
    path('item/<int:pk>/delete/', views.inventory_item_delete, name='inventory_item_delete'),
    path('movement/create/', views.stock_movement_create, name='stock_movement_create'),
]
