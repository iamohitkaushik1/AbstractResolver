from django.urls import path
from finder import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/upload/', views.upload_bib, name='upload_bib'),
    path('api/status/<str:task_id>/', views.task_status, name='task_status'),
    path('api/cancel/<str:task_id>/', views.cancel_task, name='cancel_task'),
    path('api/preview/<str:task_id>/', views.task_preview, name='task_preview'),
    path('api/edit/<str:task_id>/', views.update_entry, name='update_entry'),
    path('api/download/<str:task_id>/', views.download_bib, name='download_bib'),
]
