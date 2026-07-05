from django.urls import path

from . import views


urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('create/', views.room_create, name='room_create'),
    path('<int:pk>/edit/', views.room_update, name='room_update'),
    path('<int:pk>/delete/', views.room_delete, name='room_delete'),
    path('<int:pk>/status/<str:status>/', views.room_change_status, name='room_change_status'),
]
