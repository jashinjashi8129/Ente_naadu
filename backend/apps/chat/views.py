from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from datetime import timedelta
from apps.accounts.models import User, UserLocation
from apps.common.geo import is_valid_coord, haversine_distance, get_bounding_box
from .models import FriendRequest, Friendship, Conversation, Message, SocialNotification
from .serializers import (
    UserPublicSerializer,
    FriendRequestSerializer,
    FriendUserSerializer,
    MessageSerializer,
    SendMessageSerializer,
    ConversationSerializer,
    SocialNotificationSerializer
)


class UserDiscoveryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for searching and discovering fellow citizens in Ente Naadu.
    Excludes the authenticated user and accounts that are suspended/blocked.
    """
    serializer_class = UserPublicSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.filter(is_active=True, is_blocked=False).exclude(id=user.id).select_related('area')

        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(area__name__icontains=q)
            )

        area_id = self.request.query_params.get('area')
        if area_id and area_id.isdigit():
            qs = qs.filter(area_id=int(area_id))

        ward = self.request.query_params.get('ward')
        if ward and ward.isdigit():
            qs = qs.filter(ward_number=int(ward))

        return qs.order_by('full_name')[:50]


class FriendRequestViewSet(viewsets.ViewSet):
    """
    API for managing friend requests:
    - Send request (POST /api/v1/chat/requests/send/)
    - Incoming requests (GET /api/v1/chat/requests/incoming/)
    - Outgoing requests (GET /api/v1/chat/requests/outgoing/)
    - Accept request (POST /api/v1/chat/requests/<id>/accept/)
    - Reject request (POST /api/v1/chat/requests/<id>/reject/)
    - Cancel request (POST /api/v1/chat/requests/<id>/cancel/)
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='send')
    def send_request(self, request):
        sender = request.user
        receiver_id = request.data.get('receiver_id') or request.data.get('to_user_id')

        if not receiver_id:
            return Response({"error": "receiver_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=int(receiver_id), is_active=True, is_blocked=False)
        except (ValueError, User.DoesNotExist):
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if sender.id == receiver.id:
            return Response({"error": "നിങ്ങൾക്ക് സ്വന്തമായി ഫ്രണ്ട് റിക്വസ്റ്റ് അയക്കാൻ കഴിയില്ല."}, status=status.HTTP_400_BAD_REQUEST)

        if Friendship.are_friends(sender, receiver):
            return Response({"error": "നിങ്ങൾ ഇതിനകം സുഹൃത്തുക്കളാണ്."}, status=status.HTTP_400_BAD_REQUEST)

        # Check existing pending requests in either direction
        existing_pending = FriendRequest.get_pending_between(sender, receiver)
        if existing_pending:
            if existing_pending.sender_id == sender.id:
                return Response({"error": "ഫ്രണ്ട് റിക്വസ്റ്റ് ഇതിനകം അയച്ചിട്ടുണ്ട് (Already pending)."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": "ഈ വ്യക്തി നിങ്ങൾക്ക് ഇതിനകം റിക്വസ്റ്റ് അയച്ചിട്ടുണ്ട്. അത് സ്വീകരിക്കുക."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            friend_req = FriendRequest.objects.create(
                sender=sender,
                receiver=receiver,
                status=FriendRequest.Status.PENDING
            )
            SocialNotification.create_notification(
                recipient=receiver,
                actor=sender,
                ntype=SocialNotification.Type.FRIEND_REQUEST,
                title=f"{sender.full_name} ഫ്രണ്ട് റിക്വസ്റ്റ് അയച്ചു",
                body=f"{sender.full_name} നിങ്ങളുമായി ബന്ധപ്പെടാൻ ആഗ്രഹിക്കുന്നു.",
                link_url="/friends/"
            )

        return Response(
            FriendRequestSerializer(friend_req, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='incoming')
    def list_incoming(self, request):
        qs = FriendRequest.objects.filter(
            receiver=request.user,
            status=FriendRequest.Status.PENDING
        ).select_related('sender', 'sender__area')
        return Response(FriendRequestSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='outgoing')
    def list_outgoing(self, request):
        qs = FriendRequest.objects.filter(
            sender=request.user,
            status=FriendRequest.Status.PENDING
        ).select_related('receiver', 'receiver__area')
        return Response(FriendRequestSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept_request(self, request, pk=None):
        friend_req = get_object_or_404(FriendRequest, id=pk)

        # Security: Only recipient can accept
        if friend_req.receiver_id != request.user.id:
            raise PermissionDenied("ഈ റിക്വസ്റ്റ് സ്വീകരിക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

        if friend_req.status != FriendRequest.Status.PENDING:
            return Response({"error": f"Request is already {friend_req.status}."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            Friendship.make_friends(friend_req.sender, friend_req.receiver)
            friend_req.status = FriendRequest.Status.ACCEPTED
            friend_req.save(update_fields=['status', 'updated_at'])

            SocialNotification.create_notification(
                recipient=friend_req.sender,
                actor=request.user,
                ntype=SocialNotification.Type.FRIEND_ACCEPT,
                title=f"{request.user.full_name} ഫ്രണ്ട് റിക്വസ്റ്റ് സ്വീകരിച്ചു!",
                body=f"ഇപ്പോൾ നിങ്ങൾക്ക് {request.user.full_name}-മായി പ്രൈവറ്റ് ചാറ്റ് ചെയ്യാം.",
                link_url=f"/chat/{request.user.id}/"
            )

        return Response({
            "message": "ഫ്രണ്ട് റിക്വസ്റ്റ് സ്വീകരിച്ചു! ഇപ്പോൾ നിങ്ങൾ സുഹൃത്തുക്കളാണ്.",
            "status": "accepted"
        })

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_request(self, request, pk=None):
        friend_req = get_object_or_404(FriendRequest, id=pk)

        # Security: Only recipient can reject
        if friend_req.receiver_id != request.user.id:
            raise PermissionDenied("ഈ റിക്വസ്റ്റ് നിരസിക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

        if friend_req.status != FriendRequest.Status.PENDING:
            return Response({"error": f"Request is already {friend_req.status}."}, status=status.HTTP_400_BAD_REQUEST)

        friend_req.status = FriendRequest.Status.REJECTED
        friend_req.save(update_fields=['status', 'updated_at'])

        return Response({
            "message": "ഫ്രണ്ട് റിക്വസ്റ്റ് നിരസിച്ചു.",
            "status": "rejected"
        })

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_request(self, request, pk=None):
        friend_req = get_object_or_404(FriendRequest, id=pk)

        # Security: Only sender can cancel their own outgoing request
        if friend_req.sender_id != request.user.id:
            raise PermissionDenied("ഈ റിക്വസ്റ്റ് റദ്ദാക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

        if friend_req.status != FriendRequest.Status.PENDING:
            return Response({"error": f"Request is already {friend_req.status}."}, status=status.HTTP_400_BAD_REQUEST)

        friend_req.status = FriendRequest.Status.CANCELLED
        friend_req.save(update_fields=['status', 'updated_at'])

        return Response({
            "message": "ഫ്രണ്ട് റിക്വസ്റ്റ് റദ്ദാക്കി.",
            "status": "cancelled"
        })


class FriendshipViewSet(viewsets.ViewSet):
    """
    API for viewing and managing friends:
    - List friends (GET /api/v1/chat/friends/)
    - Unfriend (POST /api/v1/chat/friends/<user_id>/unfriend/)
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        q = request.query_params.get('q', '').strip()
        friends_qs = Friendship.get_friends_for(request.user, search_query=q)
        return Response(FriendUserSerializer(friends_qs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='nearby')
    def nearby(self, request):
        """
        Retrieves accepted friends located within a specified radius (km).
        STRICT PRIVACY ENFORCEMENT:
        1. Both users must be accepted mutual friends.
        2. Friend must have explicitly enabled location sharing (is_sharing_enabled=True, is_paused=False).
        3. Coordinates must not be stale (updated within last 24 hours).
        4. Approximate precision setting fuzzed coordinates to protect privacy.
        """
        user = request.user
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = request.query_params.get('radius', '10')

        if not lat or not lng:
            user_loc = getattr(user, 'location', None)
            if user_loc and user_loc.latitude and user_loc.longitude:
                lat = float(user_loc.latitude)
                lng = float(user_loc.longitude)
            else:
                return Response({
                    "error": "നിങ്ങളുടെ നിലവിലെ GPS സ്ഥാനം നൽകുക അല്ലെങ്കിൽ ബ്രൗസറിൽ ലൊക്കേഷൻ പെർമിഷൻ നൽകുക."
                }, status=status.HTTP_400_BAD_REQUEST)

        if not is_valid_coord(lat, lng):
            return Response({"error": "Invalid GPS coordinates."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            radius_km = float(radius)
            if radius_km <= 0 or radius_km > 100:
                radius_km = 10.0
        except ValueError:
            radius_km = 10.0

        # Only accepted mutual friends
        friends_qs = Friendship.get_friends_for(user)
        friend_ids = list(friends_qs.values_list('id', flat=True))

        if not friend_ids:
            return Response({
                "user_lat": float(lat),
                "user_lng": float(lng),
                "radius_km": radius_km,
                "friends": []
            })

        cutoff_time = timezone.now() - timedelta(hours=24)
        bbox = get_bounding_box(lat, lng, radius_km)

        eligible_locations = UserLocation.objects.filter(
            user_id__in=friend_ids,
            is_sharing_enabled=True,
            is_paused=False,
            latitude__isnull=False,
            longitude__isnull=False,
            updated_at__gte=cutoff_time
        ).select_related('user', 'user__area')

        if bbox:
            eligible_locations = eligible_locations.filter(
                latitude__gte=bbox['min_lat'],
                latitude__lte=bbox['max_lat'],
                longitude__gte=bbox['min_lon'],
                longitude__lte=bbox['max_lon']
            )

        results = []
        for loc in eligible_locations:
            f_lat, f_lon = loc.get_coordinates()
            if f_lat is None or f_lon is None:
                continue

            dist = haversine_distance(lat, lng, f_lat, f_lon)
            if dist is not None and dist <= radius_km:
                results.append({
                    "id": loc.user.id,
                    "full_name": loc.user.full_name,
                    "profile_photo": loc.user.profile_photo.url if loc.user.profile_photo else None,
                    "role_display": loc.user.get_role_display(),
                    "area_name": loc.user.area.name if loc.user.area else '',
                    "latitude": f_lat,
                    "longitude": f_lon,
                    "distance_km": dist,
                    "precision": loc.share_precision,
                    "is_approximate": loc.share_precision == 'approximate',
                    "last_updated": loc.updated_at.strftime("%I:%M %p"),
                    "chat_url": f"/chat/{loc.user.id}/"
                })

        results.sort(key=lambda x: x['distance_km'])

        return Response({
            "user_lat": float(lat),
            "user_lng": float(lng),
            "radius_km": radius_km,
            "friends": results
        })

    @action(detail=True, methods=['post'], url_path='unfriend')
    def unfriend(self, request, pk=None):
        target_user = get_object_or_404(User, id=pk)

        if not Friendship.are_friends(request.user, target_user):
            return Response({"error": "ഈ യൂസർ നിങ്ങളുടെ ഫ്രണ്ട്സ് ലിസ്റ്റിൽ ഇല്ല."}, status=status.HTTP_400_BAD_REQUEST)

        Friendship.remove_friends(request.user, target_user)

        return Response({
            "message": f"'{target_user.full_name}'-നെ ഫ്രണ്ട്സ് ലിസ്റ്റിൽ നിന്നും ഒഴിവാക്കി. മെസ്സേജ് ഹിസ്റ്ററി സുരക്ഷിതമായി സൂക്ഷിച്ചിട്ടുണ്ട്.",
            "unfriended_user_id": target_user.id
        })


class ConversationViewSet(viewsets.ViewSet):
    """
    API for one-to-one conversations and private messaging:
    - List conversations (GET /api/v1/chat/conversations/)
    - Start conversation with friend (POST /api/v1/chat/conversations/start/<friend_id>/)
    - Get messages (GET /api/v1/chat/conversations/<id>/messages/)
    - Send message (POST /api/v1/chat/conversations/<id>/messages/send/)
    - Poll new messages (GET /api/v1/chat/conversations/<id>/poll/?after=<msg_id>)
    - Mark read (POST /api/v1/chat/conversations/<id>/read/)
    - Total unread count (GET /api/v1/chat/unread-count/)
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        user = request.user
        convs = Conversation.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).select_related('user1', 'user2', 'user1__area', 'user2__area').order_by('-updated_at')
        return Response(ConversationSerializer(convs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path=r'start/(?P<friend_id>\d+)')
    def start_conversation(self, request, friend_id=None):
        friend = get_object_or_404(User, id=friend_id, is_active=True, is_blocked=False)

        # STRICT SECURITY ENFORCEMENT: Only accepted friends can chat
        if not Friendship.are_friends(request.user, friend):
            return Response(
                {"error": "സുഹൃത്തുക്കൾക്ക് മാത്രമേ പ്രൈവറ്റ് ചാറ്റ് ചെയ്യാൻ അനുവാദമുള്ളൂ. ആദ്യം ഫ്രണ്ട് റിക്വസ്റ്റ് അയക്കുക."},
                status=status.HTTP_403_FORBIDDEN
            )

        conv = Conversation.get_or_create_between(request.user, friend)
        return Response(ConversationSerializer(conv, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='messages')
    def get_messages(self, request, pk=None):
        conv = get_object_or_404(Conversation, id=pk)

        # IDOR DEFENSE: User must be a participant
        if not conv.is_participant(request.user):
            raise PermissionDenied("ഈ സംഭാഷണം കാണാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

        # Mark incoming messages as read upon viewing
        conv.mark_as_read_by(request.user)

        limit = int(request.query_params.get('limit', 100))
        messages_qs = conv.messages.all().select_related('sender').order_by('created_at')[:limit]

        other_user = conv.get_other_user(request.user)
        are_friends = Friendship.are_friends(request.user, other_user)

        return Response({
            "conversation_id": conv.id,
            "other_user": {
                "id": other_user.id,
                "full_name": other_user.full_name,
                "role_display": other_user.get_role_display(),
                "area_name": other_user.area.name if other_user.area else '',
                "profile_photo": other_user.profile_photo.url if other_user.profile_photo else None,
                "are_friends": are_friends
            },
            "messages": MessageSerializer(messages_qs, many=True, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], url_path=r'messages/send')
    def send_message(self, request, pk=None):
        conv = get_object_or_404(Conversation, id=pk)

        # IDOR DEFENSE: User must be a participant
        if not conv.is_participant(request.user):
            raise PermissionDenied("ഈ സംഭാഷണത്തിൽ മെസ്സേജ് അയക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

        other_user = conv.get_other_user(request.user)

        # STRICT PRIVACY & FRIENDSHIP POLICY ENFORCEMENT:
        # Only accepted friends can continue exchanging messages!
        if not Friendship.are_friends(request.user, other_user):
            return Response(
                {"error": "ഈ വ്യക്തി ഇപ്പോൾ നിങ്ങളുടെ ഫ്രണ്ട് അല്ല. പുതിയ മെസ്സേജുകൾ അയക്കാൻ സാധ്യമല്ല."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sanitized_text = serializer.validated_data['text']

        with transaction.atomic():
            msg = Message.objects.create(
                conversation=conv,
                sender=request.user,
                text=sanitized_text
            )
            conv.updated_at = timezone.now()
            conv.save(update_fields=['updated_at'])

            SocialNotification.create_notification(
                recipient=other_user,
                actor=request.user,
                ntype=SocialNotification.Type.NEW_MESSAGE,
                title=f"പുതിയ മെസ്സേജ്: {request.user.full_name}",
                body=f"{sanitized_text[:60]}...",
                link_url=f"/chat/{request.user.id}/"
            )

        return Response(
            MessageSerializer(msg, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], url_path='poll')
    def poll_new_messages(self, request, pk=None):
        """
        Lightweight, ultra-fast polling endpoint to fetch messages received since `after_id`.
        Allows live chatting with zero WebSocket/Redis infrastructure overhead.
        """
        conv = get_object_or_404(Conversation, id=pk)

        if not conv.is_participant(request.user):
            raise PermissionDenied("Unauthorized.")

        after_id = request.query_params.get('after', '0')
        try:
            after_id = int(after_id)
        except ValueError:
            after_id = 0

        # Mark new incoming messages as read
        conv.mark_as_read_by(request.user)

        new_messages = conv.messages.filter(id__gt=after_id).select_related('sender').order_by('created_at')

        return Response({
            "new_messages": MessageSerializer(new_messages, many=True, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        conv = get_object_or_404(Conversation, id=pk)
        if not conv.is_participant(request.user):
            raise PermissionDenied("Unauthorized.")
        updated_count = conv.mark_as_read_by(request.user)
        return Response({"marked_read": updated_count})


class NotificationViewSet(viewsets.ViewSet):
    """
    API for listing and clearing user's social notifications.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        notifications = SocialNotification.objects.filter(
            recipient=request.user
        ).select_related('actor')[:30]
        return Response(SocialNotificationSerializer(notifications, many=True).data)

    @action(detail=False, methods=['get'], url_path='unread-summary')
    def unread_summary(self, request):
        user = request.user
        unread_notifications = SocialNotification.objects.filter(recipient=user, is_read=False).count()
        pending_requests = FriendRequest.objects.filter(receiver=user, status=FriendRequest.Status.PENDING).count()

        # Unread messages across all conversations
        unread_messages = Message.objects.filter(
            conversation__in=Conversation.objects.filter(Q(user1=user) | Q(user2=user)),
            is_read=False
        ).exclude(sender=user).count()

        return Response({
            "unread_messages": unread_messages,
            "pending_requests": pending_requests,
            "unread_notifications": unread_notifications,
            "total_alerts": unread_messages + pending_requests
        })

    @action(detail=True, methods=['post'], url_path='read')
    def mark_notification_read(self, request, pk=None):
        notif = get_object_or_404(SocialNotification, id=pk, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({"status": "read"})
