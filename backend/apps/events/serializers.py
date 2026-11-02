from rest_framework import serializers
from .models import EventNotice, EventRSVP

class EventRSVPSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = EventRSVP
        fields = ['id', 'event', 'user', 'user_name', 'status', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

class EventNoticeSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    notice_type_display = serializers.CharField(source='get_notice_type_display', read_only=True)
    going_count = serializers.SerializerMethodField()
    my_rsvp = serializers.SerializerMethodField()

    class Meta:
        model = EventNotice
        fields = [
            'id',
            'area',
            'notice_type',
            'notice_type_display',
            'title',
            'description',
            'category',
            'category_display',
            'author',
            'author_name',
            'ward_number',
            'event_date',
            'venue',
            'is_emergency',
            'poster_image',
            'going_count',
            'my_rsvp',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

    def get_going_count(self, obj):
        return obj.rsvps.filter(status=EventRSVP.Status.GOING).count()

    def get_my_rsvp(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            rsvp = obj.rsvps.filter(user=request.user).first()
            return rsvp.status if rsvp else None
        return None
