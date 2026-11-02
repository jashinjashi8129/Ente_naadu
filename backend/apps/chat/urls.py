from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserDiscoveryViewSet,
    FriendRequestViewSet,
    FriendshipViewSet,
    ConversationViewSet,
    NotificationViewSet
)

# REST API Router for Mobile App & Frontend AJAX fetchers
router = DefaultRouter()
router.register(r'users', UserDiscoveryViewSet, basename='api-chat-users')
router.register(r'requests', FriendRequestViewSet, basename='api-chat-requests')
router.register(r'friends', FriendshipViewSet, basename='api-chat-friends')
router.register(r'conversations', ConversationViewSet, basename='api-chat-conversations')
router.register(r'notifications', NotificationViewSet, basename='api-chat-notifications')

urlpatterns = [
    path('unread-count/', NotificationViewSet.as_view({'get': 'unread_summary'}), name='api-chat-unread-count'),
    path('', include(router.urls)),
]
