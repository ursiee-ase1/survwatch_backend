"""
Django REST Framework serializers for surveillance app.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Camera, Alert, Video, DetectionConfig, DetectionRule


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


class ActiveCameraWithConfigSerializer(serializers.ModelSerializer):
    """Serializer for active cameras with effective detection config (used by pipeline)."""
    effective_config = serializers.SerializerMethodField()
    
    class Meta:
        model = Camera
        fields = ['id', 'rtsp_url', 'name', 'effective_config']
    
    def get_effective_config(self, obj):
        """Get effective detection config for this camera."""
        from .models import DetectionConfig
        
        config = DetectionConfig.get_effective_config_for_camera(obj)
        
        if config:
            # Get detection rules
            rules = config.detection_rules.all()
            rules_data = DetectionRuleSerializer(rules, many=True).data
            
            return {
                'monitor_mode': config.monitor_mode,
                'active_hours_start': str(config.active_hours_start) if config.active_hours_start else None,
                'active_hours_end': str(config.active_hours_end) if config.active_hours_end else None,
                'timezone': config.timezone,
                'confidence_threshold': config.confidence_threshold,
                'frame_skip': config.frame_skip,
                'detection_rules': rules_data,
                'is_system_default': False,
            }
        else:
            # Return system defaults
            defaults = DetectionConfig.get_system_defaults()
            return {
                'monitor_mode': defaults['monitor_mode'],
                'active_hours_start': None,
                'active_hours_end': None,
                'timezone': defaults['timezone'],
                'confidence_threshold': defaults['confidence_threshold'],
                'frame_skip': defaults['frame_skip'],
                'detection_rules': [],
                'is_system_default': True,
            }


class DetectionRuleSerializer(serializers.ModelSerializer):
    """Serializer for DetectionRule model."""
    effective_confidence = serializers.SerializerMethodField()
    
    class Meta:
        model = DetectionRule
        fields = [
            'id', 'object_class', 'threat_level', 'should_alert', 
            'min_confidence', 'effective_confidence'
        ]
    
    def get_effective_confidence(self, obj):
        """Get effective confidence threshold."""
        return obj.get_effective_confidence()


class DetectionConfigSerializer(serializers.ModelSerializer):
    """Serializer for DetectionConfig model."""
    detection_rules = DetectionRuleSerializer(many=True, read_only=True)
    scope = serializers.SerializerMethodField()
    
    class Meta:
        model = DetectionConfig
        fields = [
            'id', 'user', 'camera', 'scope', 'monitor_mode',
            'active_hours_start', 'active_hours_end', 'timezone',
            'confidence_threshold', 'frame_skip', 'detection_rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_scope(self, obj):
        """Return scope description."""
        if obj.camera:
            return f"Camera: {obj.camera.name}"
        elif obj.user:
            return f"User Default: {obj.user.username}"
        return "Unknown"
    
    def validate(self, data):
        """Validate that either user or camera is set, but not both."""
        user = data.get('user', self.instance.user if self.instance else None)
        camera = data.get('camera', self.instance.camera if self.instance else None)
        
        if not user and not camera:
            raise serializers.ValidationError("Either 'user' or 'camera' must be set.")
        if user and camera:
            raise serializers.ValidationError("Cannot set both 'user' and 'camera'. Choose one.")
        
        return data


class DetectionConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating DetectionConfig."""
    detection_rules = DetectionRuleSerializer(many=True, required=False)
    
    class Meta:
        model = DetectionConfig
        fields = [
            'monitor_mode', 'active_hours_start', 'active_hours_end', 'timezone',
            'confidence_threshold', 'frame_skip', 'detection_rules'
        ]
    
    def create(self, validated_data):
        """Create config and associated rules."""
        rules_data = validated_data.pop('detection_rules', [])
        config = DetectionConfig.objects.create(**validated_data)
        
        for rule_data in rules_data:
            DetectionRule.objects.create(config=config, **rule_data)
        
        return config
    
    def update(self, instance, validated_data):
        """Update config and associated rules."""
        rules_data = validated_data.pop('detection_rules', None)
        
        # Update config fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update rules if provided
        if rules_data is not None:
            # Delete existing rules
            instance.detection_rules.all().delete()
            # Create new rules
            for rule_data in rules_data:
                DetectionRule.objects.create(config=instance, **rule_data)
        
        return instance


class EffectiveDetectionConfigSerializer(serializers.Serializer):
    """Serializer for effective detection config (resolved override logic)."""
    monitor_mode = serializers.CharField()
    active_hours_start = serializers.TimeField(allow_null=True)
    active_hours_end = serializers.TimeField(allow_null=True)
    timezone = serializers.CharField()
    confidence_threshold = serializers.FloatField()
    frame_skip = serializers.IntegerField()
    detection_rules = DetectionRuleSerializer(many=True)
    is_system_default = serializers.BooleanField()


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


class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video model."""
    user = serializers.ReadOnlyField(source='user.username')
    camera_name = serializers.ReadOnlyField(source='camera.name', allow_null=True)
    video_file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Video
        fields = ['id', 'user', 'camera', 'camera_name', 'title', 'video_file', 
                 'video_file_url', 'video_type', 'description', 'duration', 
                 'file_size', 'uploaded_at', 'processed']
        read_only_fields = ['uploaded_at', 'file_size']
    
    def get_video_file_url(self, obj):
        """Get full URL for video file."""
        if obj.video_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.video_file.url)
        return None


class VideoCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating videos."""
    class Meta:
        model = Video
        fields = ['camera', 'title', 'video_file', 'video_type', 'description']
    
    def create(self, validated_data):
        """Set the user when creating a video."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

