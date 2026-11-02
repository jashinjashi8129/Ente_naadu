from django.db import models, transaction
from django.conf import settings
from django.db.models import Q, F
from django.utils import timezone
from apps.accounts.models import User

class FriendRequest(models.Model):
    """
    Tracks social connection requests between citizens in Ente Naadu.
    Enforces strict mutual agreement before private chat is permitted.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'കാത്തിരിക്കുന്നു (Pending)'
        ACCEPTED = 'accepted', 'സ്വീകരിച്ചു (Accepted)'
        REJECTED = 'rejected', 'നിരസിച്ചു (Rejected)'
        CANCELLED = 'cancelled', 'റദ്ദാക്കി (Cancelled)'

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_friend_requests',
        verbose_name="അയച്ചയാൾ (Sender)"
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_friend_requests',
        verbose_name="സ്വീകരിച്ചയാൾ (Receiver)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="സ്റ്റാറ്റസ് (Status)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ഫ്രണ്ട് റിക്വസ്റ്റ് (Friend Request)"
        verbose_name_plural = "ഫ്രണ്ട് റിക്വസ്റ്റുകൾ (Friend Requests)"
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(sender=models.F('receiver')),
                name='chat_prevent_self_friend_request'
            )
        ]

    def __str__(self):
        return f"{self.sender.full_name} -> {self.receiver.full_name} ({self.status})"

    @classmethod
    def get_pending_between(cls, user_a, user_b):
        """Returns any active pending request between two users regardless of direction."""
        return cls.objects.filter(
            Q(sender=user_a, receiver=user_b) | Q(sender=user_b, receiver=user_a),
            status=cls.Status.PENDING
        ).first()


class Friendship(models.Model):
    """
    Bidirectional accepted friendship stored as a canonical pair: user1_id < user2_id.
    Guarantees no duplicate inverted rows in the database.
    """
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friendships_as_user1',
        verbose_name="യൂസർ 1"
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='friendships_as_user2',
        verbose_name="യൂസർ 2"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "സൗഹൃദം (Friendship)"
        verbose_name_plural = "സൗഹൃദങ്ങൾ (Friendships)"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user1', 'user2'],
                name='unique_canonical_friendship'
            ),
            models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F('user2_id')),
                name='chat_canonical_friendship_order'
            )
        ]

    def __str__(self):
        return f"{self.user1.full_name} & {self.user2.full_name}"

    @classmethod
    def are_friends(cls, user_a, user_b):
        """Check if user_a and user_b are accepted friends."""
        if not user_a or not user_b or user_a.id == user_b.id:
            return False
        u1_id, u2_id = (user_a.id, user_b.id) if user_a.id < user_b.id else (user_b.id, user_a.id)
        return cls.objects.filter(user1_id=u1_id, user2_id=u2_id).exists()

    @classmethod
    def get_friends_for(cls, user, search_query=None):
        """
        Returns a QuerySet of User instances who are accepted friends with `user`.
        Supports optional search filter by name or phone.
        """
        if not user or not user.is_authenticated:
            return User.objects.none()

        friendships = cls.objects.filter(Q(user1=user) | Q(user2=user))
        friend_ids = []
        for f in friendships:
            friend_ids.append(f.user2_id if f.user1_id == user.id else f.user1_id)

        qs = User.objects.filter(id__in=friend_ids, is_active=True).select_related('area')
        if search_query:
            qs = qs.filter(
                Q(full_name__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        return qs.order_by('full_name')

    @classmethod
    def make_friends(cls, user_a, user_b):
        """Atomically creates friendship and marks requests accepted."""
        if user_a.id == user_b.id:
            raise ValueError("Users cannot friend themselves.")

        u1, u2 = (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)
        with transaction.atomic():
            friendship, created = cls.objects.get_or_create(user1=u1, user2=u2)
            # Update any existing pending requests between them to accepted
            FriendRequest.objects.filter(
                Q(sender=user_a, receiver=user_b) | Q(sender=user_b, receiver=user_a),
                status=FriendRequest.Status.PENDING
            ).update(status=FriendRequest.Status.ACCEPTED)

            # Ensure unique conversation row exists
            Conversation.get_or_create_between(user_a, user_b)

            return friendship

    @classmethod
    def create_mutual(cls, user_a, user_b):
        """Alias for make_friends."""
        return cls.make_friends(user_a, user_b)


    @classmethod
    def remove_friends(cls, user_a, user_b):
        """
        Removes friendship between two users.
        Preserves message history in Conversation/Message tables.
        """
        u1_id, u2_id = (user_a.id, user_b.id) if user_a.id < user_b.id else (user_b.id, user_a.id)
        with transaction.atomic():
            deleted_count, _ = cls.objects.filter(user1_id=u1_id, user2_id=u2_id).delete()
            # Also reset any accepted requests to cancelled so neither appears in friends list
            FriendRequest.objects.filter(
                Q(sender_id=u1_id, receiver_id=u2_id) | Q(sender_id=u2_id, receiver_id=u1_id)
            ).update(status=FriendRequest.Status.CANCELLED)
            return deleted_count > 0


class Conversation(models.Model):
    """
    A unique private conversation room between two users (canonical pair user1_id < user2_id).
    Prevents duplicate conversation threads between the same two users.
    """
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations_user1'
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations_user2'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "സംഭാഷണം (Conversation)"
        verbose_name_plural = "സംഭാഷണങ്ങൾ (Conversations)"
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user1', 'user2'],
                name='unique_canonical_conversation'
            ),
            models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F('user2_id')),
                name='chat_canonical_conversation_users'
            )
        ]

    def __str__(self):
        return f"Chat #{self.id}: {self.user1.full_name} & {self.user2.full_name}"

    @classmethod
    def get_or_create_between(cls, user_a, user_b):
        """Fetches or creates the unique canonical conversation between two users."""
        if user_a.id == user_b.id:
            raise ValueError("Cannot create a conversation with oneself.")
        u1, u2 = (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)
        conv, _ = cls.objects.get_or_create(user1=u1, user2=u2)
        return conv

    @classmethod
    def get_or_create_for(cls, user_a, user_b):
        """Alias for get_or_create_between."""
        return cls.get_or_create_between(user_a, user_b)


    def get_other_user(self, current_user):
        """Returns the participant that is not current_user."""
        return self.user2 if self.user1_id == current_user.id else self.user1

    def is_participant(self, user):
        """Security check: verify whether user is a participant."""
        if not user or not user.is_authenticated:
            return False
        return self.user1_id == user.id or self.user2_id == user.id

    def get_unread_count_for(self, user):
        """Counts unread messages sent by the other participant."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def mark_as_read_by(self, user):
        """Marks all incoming messages in this conversation as read by user."""
        now = timezone.now()
        unread_qs = self.messages.filter(is_read=False).exclude(sender=user)
        return unread_qs.update(is_read=True, read_at=now)

    @property
    def latest_message(self):
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    """
    Individual text message sent within a verified private conversation.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    text = models.TextField(max_length=2000, verbose_name="സന്ദേശം (Message)")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "സന്ദേശം (Message)"
        verbose_name_plural = "സന്ദേശങ്ങൾ (Messages)"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['conversation', 'is_read']),
        ]

    def __str__(self):
        return f"{self.sender.full_name}: {self.text[:30]}"


class SocialNotification(models.Model):
    """
    In-app social notification tracking friend requests, acceptances, and new messages.
    Zero external dependencies, zero-cost SQLite/Postgres storage.
    """
    class Type(models.TextChoices):
        FRIEND_REQUEST = 'friend_request', 'ഫ്രണ്ട് റിക്വസ്റ്റ് (Friend Request)'
        FRIEND_ACCEPT = 'friend_accept', 'സൗഹൃദം സ്വീകരിച്ചു (Friend Accepted)'
        NEW_MESSAGE = 'new_message', 'പുതിയ സന്ദേശം (New Message)'
        ORDER_UPDATE = 'order_update', 'ഓർഡർ അറിയിപ്പ് (Order Notification)'
        BOOKING_UPDATE = 'booking_update', 'ബുക്കിംഗ് അറിയിപ്പ് (Booking Notification)'
        SERVICE_UPDATE = 'service_update', 'സർവീസ് അറിയിപ്പ് (Service Notification)'
        DIRECTORY_UPDATE = 'directory_update', 'ഡയറക്ടറി അറിയിപ്പ് (Directory Notification)'
        COMPLAINT_UPDATE = 'complaint_update', 'പരാതി അറിയിപ്പ് (Complaint Notification)'
        SYSTEM_ALERT = 'system_alert', 'സിസ്റ്റം അറിയിപ്പ് (System Alert)'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_notifications'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        db_index=True
    )
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=400)
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "അറിയിപ്പ് (Notification)"
        verbose_name_plural = "അറിയിപ്പുകൾ (Notifications)"
        ordering = ['-created_at']

    def __str__(self):
        return f"To {self.recipient.full_name}: {self.title}"

    @classmethod
    def create_notification(cls, recipient, actor, ntype, title, body, link_url=''):
        """Helper to create and dispatch notification safely."""
        if recipient.id == (actor.id if actor else None):
            return None
        return cls.objects.create(
            recipient=recipient,
            actor=actor,
            notification_type=ntype,
            title=title,
            body=body,
            link_url=link_url
        )
