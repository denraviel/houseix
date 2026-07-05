from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('create/', views.ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('<int:pk>/toggle-active/', views.product_toggle_active, name='product_toggle_active'),
    path('<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
]
