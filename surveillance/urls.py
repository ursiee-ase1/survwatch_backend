"""
URL configuration for surveillance app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'cameras', views.CameraViewSet, basename='camera')
router.register(r'alerts', views.AlertViewSet, basename='alert')
router.register(r'videos', views.VideoViewSet, basename='video')

urlpatterns = [
    # Home page
    path('', views.home, name='home'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('active-cameras/', views.active_cameras, name='active-cameras'),
    path('send-alert/', views.send_alert, name='send-alert'),
    
    # Detection config endpoints
    path('cameras/<int:camera_id>/config/', views.camera_config, name='camera-config'),
    path('users/me/default-config/', views.user_default_config, name='user-default-config'),
    
    # Dashboard views
    path('dashboard/', views.dashboard, name='dashboard'),
]

