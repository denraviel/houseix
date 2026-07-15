from django.urls import path
from . import views

urlpatterns = [
    path('', views.SaleListView.as_view(), name='sales_list'),
    path('create/', views.SaleCreateView.as_view(), name='sale_create'),
    path('<int:pk>/delete/', views.SaleDeleteView.as_view(), name='sale_delete'),
]
