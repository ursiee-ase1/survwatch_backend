"""
Django REST Framework serializers for surveillance app.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Camera, Alert


class CameraSerializer(serializers.ModelSerializer):
    """Serializer for Camera model."""
    user = serializers.ReadOnlyField(source='user.username')
    
    class Meta:
        model = Camera
        fields = ['id', 'user', 'name', 'rtsp_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CameraListSerializer(serializers.ModelSerializer):
    """Simplified serializer for active cameras list (used by pipeline)."""
    class Meta:
        model = Camera
        fields = ['id', 'rtsp_url']


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model."""
    camera_name = serializers.ReadOnlyField(source='camera.name')
    
    class Meta:
        model = Alert
        fields = ['id', 'camera', 'camera_name', 'alert_type', 'confidence', 
                 'timestamp', 'image', 'description', 'acknowledged']
        read_only_fields = ['timestamp']


class AlertCreateSerializer(serializers.Serializer):
    """Serializer for creating alerts from pipeline."""
    camera_id = serializers.IntegerField()
    alert_type = serializers.ChoiceField(choices=Alert.ALERT_TYPES)
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)
    image_base64 = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_camera_id(self, value):
        """Validate that camera exists and is active."""
        try:
            camera = Camera.objects.get(id=value, is_active=True)
        except Camera.DoesNotExist:
            raise serializers.ValidationError("Camera not found or not active.")
        return value

