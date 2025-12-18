"""
Django models for surveillance system.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import pytz


class Camera(models.Model):
    """
    Camera model representing a CCTV camera.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cameras')
    name = models.CharField(max_length=200, help_text="Camera name/identifier")
    rtsp_url = models.URLField(max_length=500, help_text="RTSP stream URL")
    is_active = models.BooleanField(default=True, help_text="Whether camera is actively monitored")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Camera'
        verbose_name_plural = 'Cameras'
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class Alert(models.Model):
    """
    Alert model for storing detection alerts from the pipeline.
    """
    ALERT_TYPES = [
        ('violence', 'Violence'),
        ('intrusion', 'Intrusion'),
        ('fire', 'Fire'),
        ('smoke', 'Smoke'),
        ('person', 'Person Detected'),
        ('vehicle', 'Vehicle Detected'),
        ('suspicious', 'Suspicious Activity'),
        ('other', 'Other'),
    ]
    
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    confidence = models.FloatField(help_text="Detection confidence (0.0 to 1.0)")
    timestamp = models.DateTimeField(default=timezone.now)
    image = models.ImageField(upload_to='alerts/', blank=True, null=True, 
                             help_text="Captured frame image")
    description = models.TextField(blank=True, help_text="Additional alert details")
    acknowledged = models.BooleanField(default=False, help_text="Whether alert has been reviewed")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['camera', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} alert from {self.camera.name} @ {self.timestamp}"


class Video(models.Model):
    """
    Video model for storing uploaded test videos.
    """
    VIDEO_TYPES = [
        ('test', 'Test Video'),
        ('training', 'Training Data'),
        ('demo', 'Demo Video'),
        ('recorded', 'Recorded Footage'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name='videos', 
                              blank=True, null=True, help_text="Associated camera (optional)")
    title = models.CharField(max_length=200, help_text="Video title")
    video_file = models.FileField(upload_to='videos/', help_text="Uploaded video file")
    video_type = models.CharField(max_length=50, choices=VIDEO_TYPES, default='test')
    description = models.TextField(blank=True, help_text="Video description")
    duration = models.FloatField(blank=True, null=True, help_text="Video duration in seconds")
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="File size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False, help_text="Whether video has been processed by pipeline")
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Video'
        verbose_name_plural = 'Videos'
        indexes = [
            models.Index(fields=['-uploaded_at']),
            models.Index(fields=['user', '-uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.video_type}) - {self.user.username}"
    
    def save(self, *args, **kwargs):
        """Override save to extract file metadata."""
        if self.video_file and not self.file_size:
            self.file_size = self.video_file.size
        super().save(*args, **kwargs)


# Curated list of security-relevant COCO object classes
# Only these classes are exposed in the UI and can be configured
SECURITY_RELEVANT_COCO_CLASSES = [
    ('person', 'Person'),
    ('bicycle', 'Bicycle'),
    ('car', 'Car'),
    ('motorcycle', 'Motorcycle'),
    ('bus', 'Bus'),
    ('truck', 'Truck'),
    ('backpack', 'Backpack'),
    ('handbag', 'Handbag'),
    ('suitcase', 'Suitcase'),
    ('knife', 'Knife'),
    ('bottle', 'Bottle'),
    ('cell phone', 'Cell Phone'),
    ('laptop', 'Laptop'),
]


class DetectionConfig(models.Model):
    """
    Detection configuration model.
    Can be either user-level default OR camera-level override.
    Enforces mutual exclusivity: either user OR camera, never both.
    """
    MONITOR_MODE_CHOICES = [
        ('always', 'Always Monitor'),
        ('after_hours', 'After Hours Only'),
        ('custom', 'Custom Hours'),
    ]
    
    # Mutually exclusive: either user (default) OR camera (override)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='detection_configs',
        null=True,
        blank=True,
        help_text="User-level default config (leave blank if this is a camera override)"
    )
    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name='detection_config',
        null=True,
        blank=True,
        help_text="Camera-level override (leave blank if this is a user default)"
    )
    
    # Monitor mode and hours
    monitor_mode = models.CharField(
        max_length=20,
        choices=MONITOR_MODE_CHOICES,
        default='always',
        help_text="When to monitor: always, after hours only, or custom hours"
    )
    active_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time for active hours (required if monitor_mode is 'after_hours' or 'custom')"
    )
    active_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End time for active hours (required if monitor_mode is 'after_hours' or 'custom')"
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Timezone for active hours (e.g., 'America/New_York', 'UTC')"
    )
    
    # Detection parameters
    confidence_threshold = models.FloatField(
        default=0.6,
        help_text="Default confidence threshold (0.0 to 1.0)"
    )
    frame_skip = models.IntegerField(
        default=5,
        help_text="Number of frames to skip between detections (performance optimization)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Detection Config'
        verbose_name_plural = 'Detection Configs'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['camera']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(camera__isnull=True),
                name='unique_user_default_config'
            ),
            models.UniqueConstraint(
                fields=['camera'],
                condition=models.Q(user__isnull=True),
                name='unique_camera_override_config'
            ),
        ]
    
    def clean(self):
        """Validate that either user OR camera is set, but not both."""
        if not self.user and not self.camera:
            raise ValidationError("Either 'user' or 'camera' must be set, but not both.")
        if self.user and self.camera:
            raise ValidationError("Cannot set both 'user' and 'camera'. Choose one.")
        
        # Validate time fields based on monitor_mode
        if self.monitor_mode in ['after_hours', 'custom']:
            if not self.active_hours_start or not self.active_hours_end:
                raise ValidationError(
                    f"active_hours_start and active_hours_end are required when monitor_mode is '{self.monitor_mode}'"
                )
        
        # Validate timezone
        try:
            pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValidationError(f"Invalid timezone: {self.timezone}")
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.camera:
            return f"Detection Config (Camera: {self.camera.name})"
        elif self.user:
            return f"Detection Config (User: {self.user.username} - Default)"
        return "Detection Config (Invalid)"
    
    @staticmethod
    def get_effective_config_for_camera(camera):
        """
        Get effective detection config for a camera.
        Priority: camera override > user default > system defaults
        """
        # Try camera override first
        try:
            camera_config = DetectionConfig.objects.get(camera=camera)
            return camera_config
        except DetectionConfig.DoesNotExist:
            pass
        
        # Try user default
        try:
            user_config = DetectionConfig.objects.get(user=camera.user, camera__isnull=True)
            return user_config
        except DetectionConfig.DoesNotExist:
            pass
        
        # Return system defaults (not saved to DB, just for reference)
        return None
    
    @staticmethod
    def get_system_defaults():
        """Get system default values as a dict (for when no config exists)."""
        return {
            'monitor_mode': 'always',
            'active_hours_start': None,
            'active_hours_end': None,
            'timezone': 'UTC',
            'confidence_threshold': 0.6,
            'frame_skip': 5,
        }


class DetectionRule(models.Model):
    """
    Detection rule for specific object classes.
    Links to DetectionConfig and defines threat level and alert behavior.
    """
    THREAT_LEVEL_CHOICES = [
        ('HIGH', 'High Threat'),
        ('MEDIUM', 'Medium Threat'),
        ('LOW', 'Low Threat'),
        ('IGNORE', 'Ignore'),
    ]
    
    config = models.ForeignKey(
        DetectionConfig,
        on_delete=models.CASCADE,
        related_name='detection_rules',
        help_text="Parent detection configuration"
    )
    object_class = models.CharField(
        max_length=50,
        choices=SECURITY_RELEVANT_COCO_CLASSES,
        help_text="YOLO COCO object class name"
    )
    threat_level = models.CharField(
        max_length=10,
        choices=THREAT_LEVEL_CHOICES,
        default='MEDIUM',
        help_text="Threat level for this object class"
    )
    should_alert = models.BooleanField(
        default=True,
        help_text="Whether to send alerts for this object class"
    )
    min_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum confidence threshold for this rule (overrides config default if set)"
    )
    
    class Meta:
        verbose_name = 'Detection Rule'
        verbose_name_plural = 'Detection Rules'
        unique_together = [['config', 'object_class']]
        indexes = [
            models.Index(fields=['config', 'object_class']),
        ]
    
    def __str__(self):
        return f"{self.object_class} ({self.threat_level}) - {self.config}"
    
    def get_effective_confidence(self):
        """Get effective confidence threshold (rule-specific or config default)."""
        return self.min_confidence if self.min_confidence is not None else self.config.confidence_threshold

