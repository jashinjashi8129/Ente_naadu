from django.contrib import admin
from .models import Complaint

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'area', 'ward_number', 'citizen', 'is_anonymous', 'status', 'created_at')
    list_filter = ('status', 'category', 'area', 'ward_number', 'is_anonymous', 'created_at')
    search_fields = ('title', 'description', 'location_details', 'citizen__full_name')
    ordering = ('-created_at',)
