from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, BookingViewSet, ServiceRequestViewSet, CartViewSet

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='api-cart')
router.register(r'orders', OrderViewSet, basename='api-order')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'service-requests', ServiceRequestViewSet, basename='service-request')

urlpatterns = [
    path('', include(router.urls)),
]
