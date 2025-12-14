"""
URL configuration for surveillance app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'cameras', views.CameraViewSet, basename='camera')
router.register(r'alerts', views.AlertViewSet, basename='alert')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    path('active-cameras/', views.active_cameras, name='active-cameras'),
    path('send-alert/', views.send_alert, name='send-alert'),
    
    # Dashboard views
    path('dashboard/', views.dashboard, name='dashboard'),
]

