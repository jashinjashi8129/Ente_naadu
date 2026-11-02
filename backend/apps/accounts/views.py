from rest_framework import status, views, viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.authtoken.models import Token
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    AdminResetPasswordSerializer,
    BlockUserSerializer,
    AreaSerializer,
    AuditLogSerializer,
    UserLocationSerializer,
    UserLocationUpdateSerializer,
    LocationPreferencesSerializer,
    UserReportSerializer
)
from .models import User, Area, AuditLog, UserLocation, UserReport
from apps.shops.models import Shop
from apps.orders.models import Order
from apps.complaints.models import Complaint
from apps.common.audit import log_audit

class AreaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Area.objects.filter(is_active=True)
    serializer_class = AreaSerializer
    permission_classes = [permissions.AllowAny]

class StatusCheckView(views.APIView):
    """
    Healthcheck endpoint to wake up Render free instance.
    Frontend apps can ping this with a friendly loading indicator.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            "status": "online",
            "app": "Ente Naadu API",
            "message": "സെർവർ ഉണർന്നു പ്രവർത്തിക്കുന്നു (Server is alive and running)",
            "version": "1.0.0"
        })

class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                "message": "User registered successfully",
                "token": token.key,
                "user": UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                "token": token.key,
                "user": UserSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminBlockUserView(views.APIView):
    """
    Allows Super Admins or Ward Admins to block or unblock misbehaving users with mandatory reason logging.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN] and not request.user.is_staff:
            return Response({"error": "Admin permission required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BlockUserSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            reason = serializer.validated_data['reason']
            block = serializer.validated_data['block']

            try:
                target_user = User.objects.get(id=user_id)
                target_user.is_blocked = block
                target_user.block_reason = reason if block else ""
                target_user.save(update_fields=['is_blocked', 'block_reason'])

                # Record in AuditLog
                action_type = AuditLog.Action.BLOCK_USER if block else AuditLog.Action.UNBLOCK_USER
                AuditLog.objects.create(
                    performed_by=request.user,
                    action=action_type,
                    target_type='User',
                    target_id=target_user.id,
                    target_identifier=f"{target_user.full_name} ({target_user.phone_number})",
                    reason=reason
                )

                verb = "blocked" if block else "unblocked"
                return Response({"message": f"User {target_user.full_name} has been {verb}."})
            except User.DoesNotExist:
                return Response({"error": "Target user not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminResetPasswordView(views.APIView):
    """
    Permits Ward Admins and Super Admins to reset forgotten passwords for residents.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN] and not request.user.is_staff:
            return Response(
                {"error": "Only ward representatives and admins can reset user passwords."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                target_user = User.objects.get(id=serializer.validated_data['user_id'])
                target_user.set_password(serializer.validated_data['new_password'])
                target_user.save()

                # Audit Log
                AuditLog.objects.create(
                    performed_by=request.user,
                    action=AuditLog.Action.RESET_PASSWORD,
                    target_type='User',
                    target_id=target_user.id,
                    target_identifier=target_user.phone_number,
                    reason=serializer.validated_data.get('reason', 'Admin password reset')
                )
                return Response({"message": f"Password reset successfully for {target_user.full_name}."})
            except User.DoesNotExist:
                return Response({"error": "Target user not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminStatsDashboardView(views.APIView):
    """
    Admin Dashboard summary stats: users, shops, orders, pending complaints.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff and request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        total_users = User.objects.count()
        total_shops = Shop.objects.count()
        verified_shops = Shop.objects.filter(is_verified=True).count()
        pending_shops = Shop.objects.filter(is_verified=False).count()
        total_orders = Order.objects.count()
        pending_complaints = Complaint.objects.filter(status=Complaint.Status.SUBMITTED).count()

        return Response({
            "total_users": total_users,
            "total_shops": total_shops,
            "verified_shops": verified_shops,
            "pending_shop_approvals": pending_shops,
            "total_orders": total_orders,
            "pending_complaints": pending_complaints,
        })

class AuditLogListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        logs = AuditLog.objects.all()[:50]
        return Response(AuditLogSerializer(logs, many=True).data)


class UserLocationStatusView(views.APIView):
    """Returns the authenticated user's current location sharing status and coordinates."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        location, _ = UserLocation.objects.get_or_create(user=request.user)
        return Response(UserLocationSerializer(location).data)


class UserLocationUpdateView(views.APIView):
    """
    Updates the authenticated user's current GPS coordinates.
    Strict IDOR prevention: Always associates coordinates with request.user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location, _ = UserLocation.objects.get_or_create(user=request.user)
        location.latitude = serializer.validated_data['latitude']
        location.longitude = serializer.validated_data['longitude']
        location.save(update_fields=['latitude', 'longitude', 'updated_at'])

        data = UserLocationSerializer(location).data
        data["message"] = "ലൊക്കേഷൻ വിജയകരമായി അപ്‌ഡേറ്റ് ചെയ്തു."
        return Response(data, status=status.HTTP_200_OK)


class UserLocationPreferencesView(views.APIView):
    """
    Updates user's location sharing preferences:
    - is_sharing_enabled: ON/OFF
    - is_paused: Pause sharing temporarily
    - share_precision: exact vs approximate
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LocationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location, _ = UserLocation.objects.get_or_create(user=request.user)
        vd = serializer.validated_data
        update_fields = ['updated_at']

        if 'is_sharing_enabled' in vd:
            location.is_sharing_enabled = vd['is_sharing_enabled']
            update_fields.append('is_sharing_enabled')
        if 'is_paused' in vd:
            location.is_paused = vd['is_paused']
            update_fields.append('is_paused')
        if 'share_precision' in vd:
            location.share_precision = vd['share_precision']
            update_fields.append('share_precision')

        location.save(update_fields=update_fields)

        data = UserLocationSerializer(location).data
        data["message"] = "ലൊക്കേഷൻ ക്രമീകരണങ്ങൾ സേവ് ചെയ്തു."
        return Response(data, status=status.HTTP_200_OK)


class UserReportViewSet(viewsets.ModelViewSet):
    """
    Trust, Moderation, and Spam/Abuse control endpoint.
    - Citizens can file reports against spam, harassment, fake shops, or offensive content.
    - Citizens can view reports they themselves submitted.
    - Ward admins and super admins can view all reports, investigate, take action, or dismiss.
    - Actions taken are automatically logged to the immutable AuditLog.
    """
    queryset = UserReport.objects.all().select_related('reporter', 'reported_user', 'reviewed_by')
    serializer_class = UserReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['description', 'admin_notes', 'admin_action_taken']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            qs = super().get_queryset()
            status_param = self.request.query_params.get('status')
            reason_param = self.request.query_params.get('reason')
            content_type = self.request.query_params.get('content_type')
            if status_param:
                qs = qs.filter(status=status_param)
            if reason_param:
                qs = qs.filter(reason=reason_param)
            if content_type:
                qs = qs.filter(content_type=content_type)
            return qs
        # Regular citizens can only see reports filed by themselves
        return super().get_queryset().filter(reporter=user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    def perform_update(self, serializer):
        user = self.request.user
        if not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Only administrative staff can update moderation reports.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only administrators can delete report records.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve_report(self, request, pk=None):
        """
        Allows staff/admins to resolve a report with action taken (e.g. warned user, blocked user, removed ad).
        """
        user = request.user
        if not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Admin permission required to resolve reports.")

        report = self.get_object()
        action_taken = request.data.get('action_taken', '').strip()
        admin_notes = request.data.get('admin_notes', '').strip()

        if not action_taken:
            return Response(
                {"error": "Please specify the action taken (action_taken)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        report.status = UserReport.Status.RESOLVED
        report.admin_action_taken = action_taken
        if admin_notes:
            report.admin_notes = admin_notes
        report.reviewed_by = user
        report.save(update_fields=['status', 'admin_action_taken', 'admin_notes', 'reviewed_by', 'updated_at'])

        log_audit(
            performed_by=user,
            action=AuditLog.Action.REPORT_RESOLVE,
            target_type='UserReport',
            target_id=report.id,
            target_identifier=f"Report #{report.id} ({report.reason})",
            reason=f"Action: {action_taken}. Notes: {admin_notes}"
        )

        return Response(UserReportSerializer(report, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='dismiss')
    def dismiss_report(self, request, pk=None):
        """
        Dismisses a report if found to be frivolous or not violating community standards.
        """
        user = request.user
        if not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Admin permission required to dismiss reports.")

        report = self.get_object()
        admin_notes = request.data.get('admin_notes', '').strip()

        report.status = UserReport.Status.DISMISSED
        if admin_notes:
            report.admin_notes = admin_notes
        report.reviewed_by = user
        report.save(update_fields=['status', 'admin_notes', 'reviewed_by', 'updated_at'])

        log_audit(
            performed_by=user,
            action=AuditLog.Action.REPORT_DISMISS,
            target_type='UserReport',
            target_id=report.id,
            target_identifier=f"Report #{report.id} ({report.reason})",
            reason=f"Dismissed. Notes: {admin_notes}"
        )

        return Response(UserReportSerializer(report, context={'request': request}).data)


