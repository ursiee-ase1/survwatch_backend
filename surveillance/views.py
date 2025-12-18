"""
Django REST Framework views for surveillance app.
"""
import base64
import io
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Camera, Alert, Video, DetectionConfig, DetectionRule
from .serializers import (
    CameraSerializer, 
    CameraListSerializer,
    ActiveCameraWithConfigSerializer,
    AlertSerializer, 
    AlertCreateSerializer,
    VideoSerializer,
    VideoCreateSerializer,
    DetectionConfigSerializer,
    DetectionConfigCreateSerializer,
    DetectionRuleSerializer,
    EffectiveDetectionConfigSerializer,
)
import logging

logger = logging.getLogger(__name__)


def home(request):
    """Home page - redirects to dashboard if logged in, otherwise shows welcome page."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'surveillance/home.html')


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
    API endpoint to get list of active cameras with effective detection config.
    Used by the pipeline to fetch RTSP URLs and detection settings.
    """
    cameras = Camera.objects.filter(is_active=True).select_related('user')
    serializer = ActiveCameraWithConfigSerializer(cameras, many=True)
    logger.debug(f"Active cameras requested: {len(cameras)} cameras returned with configs")
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


class VideoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Video CRUD operations.
    """
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return videos for the authenticated user."""
        return Video.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Use different serializer for create/update operations."""
        if self.action in ['create', 'update', 'partial_update']:
            return VideoCreateSerializer
        return VideoSerializer
    
    def perform_create(self, serializer):
        """Set the user when creating a video."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Mark a video as processed by the pipeline."""
        video = self.get_object()
        video.processed = True
        video.save()
        logger.info(f"Video {video.id} marked as processed by user {request.user.username}")
        return Response({'status': 'video processed', 'video_id': video.id})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def camera_config(request, camera_id):
    """
    Get or update detection config for a specific camera.
    GET /api/cameras/<id>/config/
    PUT /api/cameras/<id>/config/
    """
    try:
        camera = Camera.objects.get(id=camera_id, user=request.user)
    except Camera.DoesNotExist:
        return Response(
            {'error': 'Camera not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        # Get effective config (camera override or user default)
        config = DetectionConfig.get_effective_config_for_camera(camera)
        
        if config and config.camera == camera:
            # Camera has its own override
            serializer = DetectionConfigSerializer(config)
            return Response(serializer.data)
        else:
            # Return effective config (might be user default or system default)
            if config:
                serializer = DetectionConfigSerializer(config)
                data = serializer.data
                data['is_override'] = False
                data['is_user_default'] = True
            else:
                # System defaults
                defaults = DetectionConfig.get_system_defaults()
                data = {
                    'monitor_mode': defaults['monitor_mode'],
                    'active_hours_start': None,
                    'active_hours_end': None,
                    'timezone': defaults['timezone'],
                    'confidence_threshold': defaults['confidence_threshold'],
                    'frame_skip': defaults['frame_skip'],
                    'detection_rules': [],
                    'is_override': False,
                    'is_user_default': False,
                    'is_system_default': True,
                }
            return Response(data)
    
    elif request.method == 'PUT':
        # Create or update camera override
        serializer = DetectionConfigCreateSerializer(
            data=request.data,
            instance=None
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if camera override already exists
        try:
            existing_config = DetectionConfig.objects.get(camera=camera)
            # Update existing
            serializer = DetectionConfigCreateSerializer(
                existing_config,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                result_serializer = DetectionConfigSerializer(existing_config)
                return Response(result_serializer.data)
        except DetectionConfig.DoesNotExist:
            # Create new override
            validated_data = serializer.validated_data
            rules_data = validated_data.pop('detection_rules', [])
            
            config = DetectionConfig.objects.create(
                camera=camera,
                **validated_data
            )
            
            for rule_data in rules_data:
                DetectionRule.objects.create(config=config, **rule_data)
            
            result_serializer = DetectionConfigSerializer(config)
            logger.info(f"Camera {camera_id} config created/updated by user {request.user.username}")
            return Response(result_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_default_config(request):
    """
    Get or update user's default detection config.
    GET /api/users/me/default-config/
    PUT /api/users/me/default-config/
    """
    if request.method == 'GET':
        try:
            config = DetectionConfig.objects.get(user=request.user, camera__isnull=True)
            serializer = DetectionConfigSerializer(config)
            return Response(serializer.data)
        except DetectionConfig.DoesNotExist:
            # Return system defaults
            defaults = DetectionConfig.get_system_defaults()
            data = {
                'monitor_mode': defaults['monitor_mode'],
                'active_hours_start': None,
                'active_hours_end': None,
                'timezone': defaults['timezone'],
                'confidence_threshold': defaults['confidence_threshold'],
                'frame_skip': defaults['frame_skip'],
                'detection_rules': [],
                'is_system_default': True,
            }
            return Response(data)
    
    elif request.method == 'PUT':
        # Create or update user default
        serializer = DetectionConfigCreateSerializer(
            data=request.data,
            instance=None
        )
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user default already exists
        try:
            existing_config = DetectionConfig.objects.get(user=request.user, camera__isnull=True)
            # Update existing
            serializer = DetectionConfigCreateSerializer(
                existing_config,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                result_serializer = DetectionConfigSerializer(existing_config)
                logger.info(f"User {request.user.username} default config updated")
                return Response(result_serializer.data)
        except DetectionConfig.DoesNotExist:
            # Create new default
            validated_data = serializer.validated_data
            rules_data = validated_data.pop('detection_rules', [])
            
            config = DetectionConfig.objects.create(
                user=request.user,
                **validated_data
            )
            
            for rule_data in rules_data:
                DetectionRule.objects.create(config=config, **rule_data)
            
            result_serializer = DetectionConfigSerializer(config)
            logger.info(f"User {request.user.username} default config created")
            return Response(result_serializer.data, status=status.HTTP_201_CREATED)


@login_required
def dashboard(request):
    """Dashboard view showing cameras, alerts, and videos."""
    cameras = Camera.objects.filter(user=request.user)
    alerts = Alert.objects.filter(camera__user=request.user).order_by('-timestamp')[:50]
    videos = Video.objects.filter(user=request.user).order_by('-uploaded_at')[:20]
    active_cameras_count = cameras.filter(is_active=True).count()
    
    context = {
        'cameras': cameras,
        'alerts': alerts,
        'videos': videos,
        'active_cameras_count': active_cameras_count,
        'total_alerts': Alert.objects.filter(camera__user=request.user).count(),
        'unacknowledged_alerts': Alert.objects.filter(
            camera__user=request.user, 
            acknowledged=False
        ).count(),
        'total_videos': Video.objects.filter(user=request.user).count(),
        'user': request.user,
    }
    return render(request, 'surveillance/dashboard.html', context)

