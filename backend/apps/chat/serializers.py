from rest_framework import serializers
from django.utils.html import escape
from apps.accounts.models import User
from .models import FriendRequest, Friendship, Conversation, Message, SocialNotification


class UserPublicSerializer(serializers.ModelSerializer):
    """
    Safe public user representation for user discovery.
    Prevents exposure of sensitive contact info, credentials, or internal flags.
    """
    area_name = serializers.CharField(source='area.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    friendship_status = serializers.SerializerMethodField()
    pending_request_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'role',
            'role_display',
            'ward_number',
            'area_name',
            'profile_photo',
            'friendship_status',
            'pending_request_id'
        ]

    def get_friendship_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return 'none'
        current_user = request.user
        if current_user.id == obj.id:
            return 'self'

        if Friendship.are_friends(current_user, obj):
            return 'friends'

        req = FriendRequest.get_pending_between(current_user, obj)
        if req:
            return 'pending_sent' if req.sender_id == current_user.id else 'pending_received'

        return 'none'

    def get_pending_request_id(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return None
        req = FriendRequest.get_pending_between(request.user, obj)
        return req.id if req else None


class FriendRequestSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for incoming and outgoing friend requests.
    """
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_role = serializers.CharField(source='sender.get_role_display', read_only=True)
    sender_area = serializers.CharField(source='sender.area.name', default='', read_only=True)
    sender_photo = serializers.SerializerMethodField()

    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    receiver_role = serializers.CharField(source='receiver.get_role_display', read_only=True)
    receiver_area = serializers.CharField(source='receiver.area.name', default='', read_only=True)
    receiver_photo = serializers.SerializerMethodField()

    is_outgoing = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = [
            'id',
            'sender_id',
            'sender_name',
            'sender_role',
            'sender_area',
            'sender_photo',
            'receiver_id',
            'receiver_name',
            'receiver_role',
            'receiver_area',
            'receiver_photo',
            'status',
            'is_outgoing',
            'created_at'
        ]

    def get_sender_photo(self, obj):
        return obj.sender.profile_photo.url if obj.sender.profile_photo else None

    def get_receiver_photo(self, obj):
        return obj.receiver.profile_photo.url if obj.receiver.profile_photo else None

    def get_is_outgoing(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return obj.sender_id == request.user.id


class FriendUserSerializer(serializers.ModelSerializer):
    """
    Detailed friend list entry with conversational metadata.
    """
    area_name = serializers.CharField(source='area.name', default='', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    conversation_id = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'role_display',
            'ward_number',
            'area_name',
            'profile_photo',
            'conversation_id',
            'unread_count',
            'last_message',
            'last_message_at'
        ]

    def _get_conversation(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return None
        return Conversation.get_or_create_between(request.user, obj)

    def get_conversation_id(self, obj):
        conv = self._get_conversation(obj)
        return conv.id if conv else None

    def get_unread_count(self, obj):
        conv = self._get_conversation(obj)
        request = self.context.get('request')
        if conv and request and request.user:
            return conv.get_unread_count_for(request.user)
        return 0

    def get_last_message(self, obj):
        conv = self._get_conversation(obj)
        if conv and conv.latest_message:
            return conv.latest_message.text[:40]
        return None

    def get_last_message_at(self, obj):
        conv = self._get_conversation(obj)
        if conv and conv.latest_message:
            return conv.latest_message.created_at
        return None


class MessageSerializer(serializers.ModelSerializer):
    """
    Represents an individual chat message safely sanitized.
    """
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_photo = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    time_formatted = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'conversation_id',
            'sender_id',
            'sender_name',
            'sender_photo',
            'text',
            'is_read',
            'read_at',
            'created_at',
            'time_formatted',
            'is_mine'
        ]

    def get_sender_photo(self, obj):
        return obj.sender.profile_photo.url if obj.sender.profile_photo else None

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return obj.sender_id == request.user.id

    def get_time_formatted(self, obj):
        return obj.created_at.strftime("%I:%M %p")


class SendMessageSerializer(serializers.Serializer):
    """
    Validates incoming chat messages. Enforces reasonable length and sanitation.
    """
    text = serializers.CharField(
        max_length=2000,
        trim_whitespace=True,
        required=True
    )

    def validate_text(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Message cannot be empty.")
        # HTML escaping to prevent XSS injection
        return escape(cleaned)


class ConversationSerializer(serializers.ModelSerializer):
    """
    Conversation overview showing the peer participant, latest activity, and unread count.
    """
    other_user = serializers.SerializerMethodField()
    latest_message_text = serializers.SerializerMethodField()
    latest_message_time = serializers.SerializerMethodField()
    latest_message_sender_id = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    are_still_friends = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'other_user',
            'latest_message_text',
            'latest_message_time',
            'latest_message_sender_id',
            'unread_count',
            'are_still_friends',
            'updated_at'
        ]

    def _get_other_user(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return None
        return obj.get_other_user(request.user)

    def get_other_user(self, obj):
        other = self._get_other_user(obj)
        if not other:
            return None
        return {
            'id': other.id,
            'full_name': other.full_name,
            'role_display': other.get_role_display(),
            'area_name': other.area.name if other.area else '',
            'ward_number': other.ward_number,
            'profile_photo': other.profile_photo.url if other.profile_photo else None
        }

    def get_latest_message_text(self, obj):
        msg = obj.latest_message
        return msg.text[:50] if msg else None

    def get_latest_message_time(self, obj):
        msg = obj.latest_message
        return msg.created_at if msg else obj.updated_at

    def get_latest_message_sender_id(self, obj):
        msg = obj.latest_message
        return msg.sender_id if msg else None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.get_unread_count_for(request.user)
        return 0

    def get_are_still_friends(self, obj):
        request = self.context.get('request')
        other = self._get_other_user(obj)
        if request and request.user and other:
            return Friendship.are_friends(request.user, other)
        return False


class SocialNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for in-app social alerts.
    """
    actor_name = serializers.CharField(source='actor.full_name', default='', read_only=True)
    actor_photo = serializers.SerializerMethodField()
    time_formatted = serializers.SerializerMethodField()

    class Meta:
        model = SocialNotification
        fields = [
            'id',
            'notification_type',
            'title',
            'body',
            'link_url',
            'is_read',
            'actor_id',
            'actor_name',
            'actor_photo',
            'created_at',
            'time_formatted'
        ]

    def get_actor_photo(self, obj):
        return obj.actor.profile_photo.url if (obj.actor and obj.actor.profile_photo) else None

    def get_time_formatted(self, obj):
        return obj.created_at.strftime("%d %b, %I:%M %p")
