"""
Django REST Framework views for surveillance app.
"""
import base64
import io
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Camera, Alert
from .serializers import (
    CameraSerializer, 
    CameraListSerializer,
    AlertSerializer, 
    AlertCreateSerializer
)
import logging

logger = logging.getLogger(__name__)


class CameraViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Camera CRUD operations.
    """
    serializer_class = CameraSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return cameras for the authenticated user."""
        return Camera.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set the user when creating a camera."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a camera."""
        camera = self.get_object()
        camera.is_active = True
        camera.save()
        logger.info(f"Camera {camera.id} activated by user {request.user.username}")
        return Response({'status': 'camera activated', 'camera_id': camera.id})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a camera."""
        camera = self.get_object()
        camera.is_active = False
        camera.save()
        logger.info(f"Camera {camera.id} deactivated by user {request.user.username}")
        return Response({'status': 'camera deactivated', 'camera_id': camera.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_cameras(request):
    """
    API endpoint to get list of active cameras.
    Used by the pipeline to fetch RTSP URLs.
    """
    cameras = Camera.objects.filter(is_active=True)
    serializer = CameraListSerializer(cameras, many=True)
    logger.debug(f"Active cameras requested: {len(cameras)} cameras returned")
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_alert(request):
    """
    API endpoint for pipeline to send alerts.
    Accepts alert data and optionally a base64-encoded image.
    """
    serializer = AlertCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning(f"Invalid alert data: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    camera_id = data['camera_id']
    
    try:
        camera = Camera.objects.get(id=camera_id, is_active=True)
    except Camera.DoesNotExist:
        logger.error(f"Camera {camera_id} not found or inactive")
        return Response(
            {'error': 'Camera not found or inactive'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Create alert
    alert = Alert.objects.create(
        camera=camera,
        alert_type=data['alert_type'],
        confidence=data['confidence'],
        description=data.get('description', ''),
    )
    
    # Handle base64 image if provided
    if data.get('image_base64'):
        try:
            image_data = base64.b64decode(data['image_base64'])
            image_file = ContentFile(image_data, name=f"alert_{alert.id}.jpg")
            alert.image = image_file
            alert.save()
            logger.info(f"Alert {alert.id} created with image for camera {camera_id}")
        except Exception as e:
            logger.error(f"Failed to save alert image: {e}")
            # Continue without image if decoding fails
    
    logger.info(f"Alert created: {alert.id} - {alert.alert_type} from camera {camera_id}")
    
    return Response({
        'status': 'alert created',
        'alert_id': alert.id,
        'camera_id': camera_id,
    }, status=status.HTTP_201_CREATED)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing alerts.
    """
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return alerts for cameras owned by the user."""
        user_cameras = Camera.objects.filter(user=self.request.user)
        return Alert.objects.filter(camera__in=user_cameras)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Mark an alert as acknowledged."""
        alert = self.get_object()
        alert.acknowledged = True
        alert.save()
        logger.info(f"Alert {alert.id} acknowledged by user {request.user.username}")
        return Response({'status': 'alert acknowledged', 'alert_id': alert.id})
    
    @action(detail=False, methods=['get'])
    def unacknowledged(self, request):
        """Get all unacknowledged alerts."""
        queryset = self.get_queryset().filter(acknowledged=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@login_required
def dashboard(request):
    """Dashboard view showing cameras and alerts."""
    cameras = Camera.objects.filter(user=request.user)
    alerts = Alert.objects.filter(camera__user=request.user).order_by('-timestamp')[:50]
    active_cameras_count = cameras.filter(is_active=True).count()
    
    context = {
        'cameras': cameras,
        'alerts': alerts,
        'active_cameras_count': active_cameras_count,
        'total_alerts': Alert.objects.filter(camera__user=request.user).count(),
        'unacknowledged_alerts': Alert.objects.filter(
            camera__user=request.user, 
            acknowledged=False
        ).count(),
    }
    return render(request, 'surveillance/dashboard.html', context)

