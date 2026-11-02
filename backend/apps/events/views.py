from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .models import EventNotice, EventRSVP
from .serializers import EventNoticeSerializer, EventRSVPSerializer
from apps.accounts.models import User

class EventNoticeViewSet(viewsets.ModelViewSet):
    queryset = EventNotice.objects.all().select_related('author').prefetch_related('rsvps')
    serializer_class = EventNoticeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'venue']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        notice_type = self.request.query_params.get('notice_type') or self.request.query_params.get('type')
        category = self.request.query_params.get('category')
        ward = self.request.query_params.get('ward')
        area = self.request.query_params.get('area')
        is_emergency = self.request.query_params.get('emergency')

        if notice_type:
            qs = qs.filter(notice_type=notice_type)
        if category:
            qs = qs.filter(category=category)
        if area:
            qs = qs.filter(area_id=area)
        if ward:
            qs = qs.filter(ward_number__in=[ward, None])
        if is_emergency:
            qs = qs.filter(is_emergency=is_emergency.lower() in ('true', '1'))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        is_emergency = serializer.validated_data.get('is_emergency', False)
        if is_emergency and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN] and not user.is_staff:
            is_emergency = False
        serializer.save(author=user, is_emergency=is_emergency)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.author != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only edit your own notices.")

        is_emergency = serializer.validated_data.get('is_emergency', instance.is_emergency)
        if is_emergency and not instance.is_emergency and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN] and not user.is_staff:
            is_emergency = False
        serializer.save(is_emergency=is_emergency)

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.author != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete your own notices.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='rsvp')
    def set_rsvp(self, request, pk=None):
        event = self.get_object()
        user = request.user
        rsvp_status = request.data.get('status', EventRSVP.Status.GOING)

        if rsvp_status not in EventRSVP.Status.values:
            return Response({"error": "Invalid RSVP status"}, status=status.HTTP_400_BAD_REQUEST)

        rsvp, _ = EventRSVP.objects.update_or_create(
            event=event,
            user=user,
            defaults={'status': rsvp_status}
        )
        return Response(EventRSVPSerializer(rsvp).data)
