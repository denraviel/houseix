from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('sales/', views.sales_report, name='sales_report'),
    path('inventory/', views.inventory_report, name='inventory_report'),
    path('products/', views.product_performance_report, name='product_performance_report'),
    path('staff/', views.staff_performance_report, name='staff_performance_report'),
    path('activity/', views.activity_report, name='activity_report'),
]
