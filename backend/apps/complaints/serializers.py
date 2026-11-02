from rest_framework import serializers
from .models import Complaint

class ComplaintSerializer(serializers.ModelSerializer):
    citizen_name = serializers.SerializerMethodField()
    citizen_phone = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Complaint
        fields = [
            'id',
            'area',
            'citizen',
            'citizen_name',
            'citizen_phone',
            'title',
            'description',
            'category',
            'category_display',
            'ward_number',
            'location_details',
            'latitude',
            'longitude',
            'photo',
            'is_anonymous',
            'status',
            'status_display',
            'admin_remarks',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'citizen', 'status', 'admin_remarks', 'created_at', 'updated_at']

    def get_citizen_name(self, obj):
        if obj.is_anonymous:
            request = self.context.get('request')
            if request and (request.user.is_staff or request.user.role in ['super_admin', 'ward_admin']):
                return f"{obj.citizen.full_name} (രഹസ്യമായി സമർപ്പിച്ചത്)"
            return "രഹസ്യ ഉപയോക്താവ് (Anonymous Citizen)"
        return obj.citizen.full_name

    def get_citizen_phone(self, obj):
        request = self.context.get('request')
        if request and (request.user.is_staff or request.user.role in ['super_admin', 'ward_admin']):
            return obj.citizen.phone_number
        return None
