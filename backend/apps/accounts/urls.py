from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StatusCheckView,
    RegisterView,
    LoginView,
    ProfileView,
    AdminResetPasswordView,
    AdminBlockUserView,
    AdminStatsDashboardView,
    AuditLogListView,
    AreaViewSet,
    UserLocationStatusView,
    UserLocationUpdateView,
    UserLocationPreferencesView,
    UserReportViewSet
)

router = DefaultRouter()
router.register(r'areas', AreaViewSet, basename='area')
router.register(r'reports', UserReportViewSet, basename='user-report')

urlpatterns = [
    path('status/', StatusCheckView.as_view(), name='status-check'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('admin-reset-password/', AdminResetPasswordView.as_view(), name='admin-reset-password'),
    path('admin-block-user/', AdminBlockUserView.as_view(), name='admin-block-user'),
    path('admin-stats/', AdminStatsDashboardView.as_view(), name='admin-stats'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit-logs'),
    path('location/status/', UserLocationStatusView.as_view(), name='api-location-status'),
    path('location/update/', UserLocationUpdateView.as_view(), name='api-location-update'),
    path('location/preferences/', UserLocationPreferencesView.as_view(), name='api-location-preferences'),
    path('user/location/status/', UserLocationStatusView.as_view(), name='user-location-status'),
    path('user/location/update/', UserLocationUpdateView.as_view(), name='user-location-update'),
    path('user/location/preferences/', UserLocationPreferencesView.as_view(), name='user-location-preferences'),
    path('', include(router.urls)),
]
