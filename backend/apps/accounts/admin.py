from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Area, AuditLog, UserLocation

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'district', 'state', 'pincode', 'is_active', 'created_at')
    list_filter = ('district', 'is_active')
    search_fields = ('name', 'district', 'pincode')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone_number', 'full_name', 'role', 'area', 'ward_number', 'is_blocked', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_blocked', 'is_staff', 'is_active', 'area', 'ward_number')
    search_fields = ('phone_number', 'full_name')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('വ്യക്തിഗത വിവരങ്ങൾ (Personal Info)', {'fields': ('full_name', 'role', 'area', 'ward_number', 'address', 'profile_photo')}),
        ('നിയന്ത്രണങ്ങൾ (Moderation)', {'fields': ('is_blocked', 'block_reason')}),
        ('അനുമതികൾ (Permissions)', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('പ്രധാന തീയതികൾ (Dates)', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    readonly_fields = ('created_at', 'updated_at')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'role', 'area', 'ward_number', 'password'),
        }),
    )

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'performed_by', 'target_identifier', 'reason')
    list_filter = ('action', 'target_type', 'timestamp')
    search_fields = ('target_identifier', 'reason', 'performed_by__full_name')
    readonly_fields = ('performed_by', 'action', 'target_type', 'target_id', 'target_identifier', 'reason', 'timestamp')

@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'latitude', 'longitude', 'is_sharing_enabled', 'is_paused', 'share_precision', 'updated_at')
    list_filter = ('is_sharing_enabled', 'is_paused', 'share_precision', 'updated_at')
    search_fields = ('user__full_name', 'user__phone_number')
    readonly_fields = ('updated_at',)

