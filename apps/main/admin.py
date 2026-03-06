# apps/main/admin.py
from django.contrib import admin
from .models import UserProfile, DirectorMessage, ActivityLog, RainDay


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'owner', 'role', 'max_warehouses', 'needs_company_setup']
    list_filter = ['role']
    search_fields = ['user__username']


@admin.register(DirectorMessage)
class DirectorMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['subject', 'message']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['description', 'user__username']
    readonly_fields = ['user', 'action', 'description', 'created_at']


@admin.register(RainDay)
class RainDayAdmin(admin.ModelAdmin):
    list_display = ['owner', 'date']
    list_filter = ['date']
