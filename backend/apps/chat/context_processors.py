from django.db.models import Q
from .models import FriendRequest, Conversation, Message

def chat_context(request):
    """
    Supplies real-time badge counts to base layout for navbar notifications.
    Optimized with fast, indexed queries.
    """
    if not request.user.is_authenticated:
        return {
            'chat_unread_count': 0,
            'pending_friend_requests_count': 0,
            'social_alerts_total': 0
        }

    user = request.user
    pending_count = FriendRequest.objects.filter(
        receiver=user,
        status=FriendRequest.Status.PENDING
    ).count()

    unread_msg_count = Message.objects.filter(
        conversation__in=Conversation.objects.filter(Q(user1=user) | Q(user2=user)),
        is_read=False
    ).exclude(sender=user).count()

    return {
        'chat_unread_count': unread_msg_count,
        'pending_friend_requests_count': pending_count,
        'social_alerts_total': unread_msg_count + pending_count
    }
