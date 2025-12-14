"""
Django models for surveillance system.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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

