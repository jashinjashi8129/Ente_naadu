from django.http import Http404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from .models import Complaint
from .serializers import ComplaintSerializer
from apps.accounts.models import User, AuditLog
from apps.chat.models import SocialNotification
from apps.common.audit import log_audit

class ComplaintViewSet(viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        ward = self.request.query_params.get('ward')
        category = self.request.query_params.get('category')
        status_filter = self.request.query_params.get('status')

        # Super admin and ward admins can see all or their ward's complaints
        if user.is_staff or user.role == User.Role.SUPER_ADMIN:
            qs = Complaint.objects.all()
        elif user.role == User.Role.WARD_ADMIN:
            qs = Complaint.objects.filter(ward_number=user.ward_number) if user.ward_number else Complaint.objects.all()
        else:
            # Citizens can see their own complaints OR resolved public issues in their ward
            qs = Complaint.objects.filter(
                Q(citizen=user) | Q(ward_number=user.ward_number, status=Complaint.Status.RESOLVED)
            )

        if ward:
            qs = qs.filter(ward_number=ward)
        if category:
            qs = qs.filter(category=category)
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def get_object(self):
        pk = self.kwargs.get('pk')
        try:
            obj = Complaint.objects.get(pk=pk)
        except (Complaint.DoesNotExist, ValueError):
            raise Http404("Complaint not found.")

        self.check_object_permissions(self.request, obj)
        user = self.request.user

        # For mutation actions (edit, delete): verify ownership or admin privileges (BOLA/IDOR protection)
        if self.action in ['update', 'partial_update', 'destroy']:
            if obj.citizen != user and not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
                raise PermissionDenied("You do not have permission to modify or delete this complaint.")
            return obj

        # For read actions (retrieve): preserve privacy
        if not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            if obj.citizen != user and not (obj.ward_number == user.ward_number and obj.status == Complaint.Status.RESOLVED):
                raise Http404("Complaint not found.")

        return obj

    def perform_create(self, serializer):
        serializer.save(citizen=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.citizen != user and not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("You can only edit your own complaints.")
        if instance.status != Complaint.Status.SUBMITTED and not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Complaints currently under review or resolved cannot be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.citizen != user and not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("You can only delete your own complaints.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """
        Allows Ward Member or Admin to change complaint progress and add remarks.
        """
        user = request.user
        if not user.is_staff and user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Only ward administrators can update complaint status.")

        complaint = self.get_object()
        new_status = request.data.get('status')
        remarks = request.data.get('remarks', '')

        if new_status:
            if new_status not in Complaint.Status.values:
                return Response(
                    {"error": f"Invalid status. Choose from: {list(Complaint.Status.values)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            complaint.status = new_status

        if remarks:
            complaint.admin_remarks = remarks

        complaint.save()

        # Audit log for civic transparency
        log_audit(
            performed_by=user,
            action=AuditLog.Action.COMPLAINT_RESOLVE if complaint.status == Complaint.Status.RESOLVED else 'complaint_status_update',
            target_type='Complaint',
            target_id=complaint.id,
            target_identifier=complaint.title,
            reason=f"Status set to {complaint.status}. Remarks: {remarks[:100]}"
        )

        # Notify the citizen about status change and official response
        SocialNotification.create_notification(
            recipient=complaint.citizen,
            actor=user,
            ntype=SocialNotification.Type.COMPLAINT_UPDATE,
            title=f"പരാതി അപ്ഡേറ്റ്: {complaint.title[:40]}",
            body=f"സ്റ്റാറ്റസ്: {complaint.get_status_display()}. {remarks[:80] if remarks else ''}",
            link_url=f"/complaints/{complaint.id}/"
        )

        return Response(ComplaintSerializer(complaint, context={'request': request}).data)
