"""
Django admin configuration for surveillance app.
"""
from django.contrib import admin
from django.forms import ModelForm, TimeInput
from django.utils.html import format_html
from .models import Camera, Alert, Video, DetectionConfig, DetectionRule


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    """Admin interface for Camera model."""
    list_display = ['name', 'user', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'user']
    search_fields = ['name', 'rtsp_url', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'rtsp_url')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    """Admin interface for Alert model."""
    list_display = ['alert_type', 'camera', 'confidence', 'timestamp', 'acknowledged']
    list_filter = ['alert_type', 'acknowledged', 'timestamp', 'camera']
    search_fields = ['camera__name', 'alert_type', 'description']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    fieldsets = (
        ('Alert Information', {
            'fields': ('camera', 'alert_type', 'confidence', 'timestamp')
        }),
        ('Details', {
            'fields': ('description', 'image', 'acknowledged')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('camera', 'camera__user')


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Admin interface for Video model."""
    list_display = ['title', 'user', 'video_type', 'processed', 'uploaded_at']
    list_filter = ['video_type', 'processed', 'uploaded_at', 'user']
    search_fields = ['title', 'description', 'user__username', 'camera__name']
    readonly_fields = ['uploaded_at', 'file_size']
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'camera', 'title', 'video_file', 'video_type')
        }),
        ('Details', {
            'fields': ('description', 'duration', 'file_size')
        }),
        ('Status', {
            'fields': ('processed',)
        }),
        ('Timestamps', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'camera')


class DetectionRuleInline(admin.TabularInline):
    """Inline admin for DetectionRule."""
    model = DetectionRule
    extra = 1
    fields = ['object_class', 'threat_level', 'should_alert', 'min_confidence']
    verbose_name = 'Detection Rule'
    verbose_name_plural = 'Detection Rules'


@admin.register(DetectionConfig)
class DetectionConfigAdmin(admin.ModelAdmin):
    """Admin interface for DetectionConfig model."""
    list_display = ['scope_display', 'monitor_mode', 'confidence_threshold', 'timezone', 'created_at']
    list_filter = ['monitor_mode', 'timezone', 'created_at']
    search_fields = ['user__username', 'camera__name']
    readonly_fields = ['created_at', 'updated_at', 'scope_display']
    inlines = [DetectionRuleInline]
    
    fieldsets = (
        ('Scope', {
            'fields': ('scope_display', 'user', 'camera'),
            'description': 'Either set User (default for all cameras) OR Camera (override for specific camera), but not both.'
        }),
        ('Monitor Mode', {
            'fields': ('monitor_mode', 'active_hours_start', 'active_hours_end', 'timezone'),
            'description': 'Configure when monitoring should be active. "After Hours" means monitor only outside active hours.'
        }),
        ('Detection Parameters', {
            'fields': ('confidence_threshold', 'frame_skip'),
            'description': 'Default confidence threshold and frame skip rate for performance optimization.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def scope_display(self, obj):
        """Display scope information."""
        if obj.camera:
            return format_html(
                '<strong style="color: #d2691e;">Camera Override:</strong> {}',
                obj.camera.name
            )
        elif obj.user:
            return format_html(
                '<strong style="color: #8b4513;">User Default:</strong> {} (applies to all cameras)',
                obj.user.username
            )
        return "Invalid (no scope set)"
    scope_display.short_description = 'Configuration Scope'
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form to show helpful labels."""
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['active_hours_start'].widget = TimeInput(attrs={'type': 'time'})
        form.base_fields['active_hours_end'].widget = TimeInput(attrs={'type': 'time'})
        return form
    
    def save_model(self, request, obj, form, change):
        """Set user or camera based on form data."""
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'camera').prefetch_related('detection_rules')


@admin.register(DetectionRule)
class DetectionRuleAdmin(admin.ModelAdmin):
    """Admin interface for DetectionRule model."""
    list_display = ['object_class', 'config_scope', 'threat_level', 'should_alert', 'min_confidence', 'effective_confidence']
    list_filter = ['threat_level', 'should_alert', 'object_class']
    search_fields = ['object_class', 'config__user__username', 'config__camera__name']
    readonly_fields = ['effective_confidence']
    
    fieldsets = (
        ('Rule Configuration', {
            'fields': ('config', 'object_class', 'threat_level', 'should_alert'),
            'description': 'Configure detection behavior for specific object classes.'
        }),
        ('Confidence Threshold', {
            'fields': ('min_confidence', 'effective_confidence'),
            'description': 'Rule-specific confidence threshold. If not set, uses config default.'
        }),
    )
    
    def config_scope(self, obj):
        """Display config scope."""
        if obj.config.camera:
            return f"Camera: {obj.config.camera.name}"
        elif obj.config.user:
            return f"User: {obj.config.user.username}"
        return "Unknown"
    config_scope.short_description = 'Config Scope'
    
    def effective_confidence(self, obj):
        """Display effective confidence threshold."""
        return obj.get_effective_confidence()
    effective_confidence.short_description = 'Effective Confidence'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('config', 'config__user', 'config__camera')

