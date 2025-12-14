"""
Django admin configuration for surveillance app.
"""
from django.contrib import admin
from .models import Camera, Alert


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

