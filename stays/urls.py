from django.urls import path

from . import views


urlpatterns = [
    path('', views.stay_list, name='stay_list'),
    path('create/', views.stay_create, name='stay_create'),
    path('<int:pk>/', views.stay_detail, name='stay_detail'),
    path('<int:pk>/edit/', views.stay_update, name='stay_update'),
    path('<int:pk>/status/', views.stay_status_update, name='stay_status_update'),
]
