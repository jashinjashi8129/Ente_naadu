from django.contrib import admin
from .models import EventNotice, EventRSVP

class EventRSVPInline(admin.TabularInline):
    model = EventRSVP
    extra = 0
    readonly_fields = ('user', 'status', 'created_at')

@admin.register(EventNotice)
class EventNoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'area', 'ward_number', 'event_date', 'is_emergency', 'created_at')
    list_filter = ('category', 'is_emergency', 'area', 'ward_number', 'created_at')
    search_fields = ('title', 'description', 'venue')
    inlines = [EventRSVPInline]
    ordering = ('-is_emergency', '-created_at')

@admin.register(EventRSVP)
class EventRSVPAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('event__title', 'user__full_name')
