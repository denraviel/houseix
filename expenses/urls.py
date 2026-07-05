from django.urls import path

from . import views


urlpatterns = [
    path('', views.ExpenseDashboardView.as_view(), name='expense_dashboard'),
    path('list/', views.ExpenseListView.as_view(), name='expense_list'),
    path('create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('<int:pk>/edit/', views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    path('<int:pk>/approve/', views.ExpenseApprovalView.as_view(), name='expense_approval'),
    path('categories/', views.ExpenseCategoryListView.as_view(), name='expense_category_list'),
    path('categories/create/', views.ExpenseCategoryCreateView.as_view(), name='expense_category_create'),
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/create/', views.VendorCreateView.as_view(), name='vendor_create'),
    path('recurring/', views.RecurringExpenseListView.as_view(), name='recurring_expense_list'),
    path('recurring/create/', views.RecurringExpenseCreateView.as_view(), name='recurring_expense_create'),
    path('recurring/generate/', views.RecurringExpenseGenerateView.as_view(), name='recurring_expense_generate'),
    path('fuel/', views.FuelLogListView.as_view(), name='fuel_log_list'),
    path('fuel/create/', views.FuelLogCreateView.as_view(), name='fuel_log_create'),
]
