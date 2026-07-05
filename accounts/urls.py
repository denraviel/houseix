from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('first-login-setup/', views.FirstLoginSetupView.as_view(), name='first_login_setup'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('employee-dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('account-settings/', views.AccountSettingsView.as_view(), name='account_settings'),
    path('account-settings/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('account-settings/change-email/', views.ChangeEmailView.as_view(), name='change_email'),
    path('account-settings/change-username/', views.ChangeUsernameView.as_view(), name='change_username'),
    path('staff/', views.StaffListView.as_view(), name='staff_list'),
    path('staff/create/', views.StaffCreateView.as_view(), name='staff_create'),
    path('staff/<int:pk>/edit/', views.StaffUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/reset-password/', views.ResetPasswordView.as_view(), name='staff_reset_password'),
    path('staff/<int:pk>/delete/', views.StaffDeleteView.as_view(), name='staff_delete'),
    path('staff/<int:pk>/toggle-active/', views.toggle_staff_active, name='toggle_staff_active'),
]
