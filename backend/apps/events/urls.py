from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventNoticeViewSet

router = DefaultRouter()
router.register(r'notices', EventNoticeViewSet, basename='notice')
router.register(r'', EventNoticeViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
]
