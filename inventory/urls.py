from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('item/create/', views.inventory_item_create, name='inventory_item_create'),
    path('movement/create/', views.stock_movement_create, name='stock_movement_create'),
]
