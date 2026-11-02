from django.db import models
from django.db.models import Q
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import DirectoryEntry, BloodDonor, ClassifiedAd, JobListing, JobApplication
from .serializers import (
    DirectoryEntrySerializer,
    BloodDonorSerializer,
    ClassifiedAdSerializer,
    JobListingSerializer,
    JobApplicationSerializer
)
from apps.accounts.models import User
from apps.chat.models import Conversation, SocialNotification
from apps.common.audit import log_audit
from apps.accounts.models import AuditLog

class DirectoryEntryViewSet(viewsets.ModelViewSet):
    queryset = DirectoryEntry.objects.all().select_related('submitted_by', 'area')
    serializer_class = DirectoryEntrySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'address_or_stand', 'phone_number']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = DirectoryEntry.objects.all().select_related('submitted_by', 'area')

        # Public users only see verified entries; users see verified + their own submitted entries; admins see all
        if not user.is_authenticated or (not user.is_staff and user.role != User.Role.SUPER_ADMIN):
            if user.is_authenticated:
                qs = qs.filter(Q(is_verified=True) | Q(submitted_by=user))
            else:
                qs = qs.filter(is_verified=True)

        category = self.request.query_params.get('category')
        ward = self.request.query_params.get('ward')
        area = self.request.query_params.get('area')
        is_emergency = self.request.query_params.get('emergency')
        verified = self.request.query_params.get('verified')

        if category:
            qs = qs.filter(category=category)
        if area:
            qs = qs.filter(area_id=area)
        if ward:
            qs = qs.filter(ward_number=ward)
        if is_emergency:
            qs = qs.filter(is_emergency_service=is_emergency.lower() in ('true', '1'))
        if verified is not None:
            qs = qs.filter(is_verified=verified.lower() in ('true', '1'))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        is_admin = user.is_staff or user.role == User.Role.SUPER_ADMIN
        is_verified = is_admin
        is_emergency = serializer.validated_data.get('is_emergency_service', False) if is_admin else False
        serializer.save(
            submitted_by=user,
            is_verified=is_verified,
            is_emergency_service=is_emergency
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        is_admin = user.is_staff or user.role == User.Role.SUPER_ADMIN
        if instance.submitted_by != user and not is_admin:
            raise PermissionDenied("You can only edit your own submitted directory entries.")

        # Re-require verification if edited by regular user
        is_verified = instance.is_verified if is_admin else False
        is_emergency = serializer.validated_data.get('is_emergency_service', instance.is_emergency_service) if is_admin else False
        serializer.save(is_verified=is_verified, is_emergency_service=is_emergency)

    def perform_destroy(self, instance):
        user = self.request.user
        is_admin = user.is_staff or user.role == User.Role.SUPER_ADMIN
        if instance.submitted_by != user and not is_admin:
            raise PermissionDenied("You can only delete your own submitted directory entries.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_entry(self, request, pk=None):
        if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Admin permission required to approve directory entries.")
        entry = self.get_object()
        entry.is_verified = True
        entry.save(update_fields=['is_verified'])
        return Response({"message": f"Directory entry '{entry.name}' verified and approved."})

    @action(detail=True, methods=['post'], url_path='reject')
    def reject_entry(self, request, pk=None):
        if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Admin permission required to reject directory entries.")
        entry = self.get_object()
        name = entry.name
        entry.delete()
        return Response({"message": f"Directory entry '{name}' rejected and removed."})

class BloodDonorViewSet(viewsets.ModelViewSet):
    queryset = BloodDonor.objects.filter(is_available=True)
    serializer_class = BloodDonorSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'phone_number', 'blood_group']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        blood_group = self.request.query_params.get('group')
        ward = self.request.query_params.get('ward')
        area = self.request.query_params.get('area')

        if blood_group:
            qs = qs.filter(blood_group=blood_group.upper().strip())
        if area:
            qs = qs.filter(area_id=area)
        if ward:
            qs = qs.filter(ward_number=ward)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(user=user)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.user != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only edit your own blood donor profile.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.user != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete your own blood donor profile.")
        instance.delete()

class ClassifiedAdViewSet(viewsets.ModelViewSet):
    queryset = ClassifiedAd.objects.all().select_related('author', 'area')
    serializer_class = ClassifiedAdSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'contact_phone', 'location', 'price_or_salary']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = ClassifiedAd.objects.all().select_related('author', 'area')

        # Public users only see approved ads; authors see their own ads
        if not user.is_authenticated or (not user.is_staff and user.role != User.Role.SUPER_ADMIN):
            if user.is_authenticated:
                qs = qs.filter(Q(is_approved=True) | Q(author=user))
            else:
                qs = qs.filter(is_approved=True)

        ad_type = self.request.query_params.get('type')
        area = self.request.query_params.get('area')
        condition = self.request.query_params.get('condition')
        location = self.request.query_params.get('location')
        if ad_type:
            qs = qs.filter(ad_type=ad_type)
        if area:
            qs = qs.filter(area_id=area)
        if condition:
            qs = qs.filter(condition=condition)
        if location:
            qs = qs.filter(location__icontains=location)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        is_approved = user.is_staff or user.role == User.Role.SUPER_ADMIN
        serializer.save(author=user, is_approved=is_approved)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.author != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only edit your own classified ads.")
        # Re-require approval if edited by regular user
        is_approved = instance.is_approved
        if not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            is_approved = False
        serializer.save(is_approved=is_approved)

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.author != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete your own classified ads.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_ad(self, request, pk=None):
        if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Admin permission required to approve classified ads.")
        ad = self.get_object()
        ad.is_approved = True
        ad.save(update_fields=['is_approved'])
        return Response({"message": f"Classified ad '{ad.title}' approved."})

    @action(detail=True, methods=['post'], url_path='contact-seller')
    def contact_seller(self, request, pk=None):
        """
        Enables instant private chat with the seller of the second-hand or classified listing.
        """
        ad = self.get_object()
        if not ad.is_approved and ad.author_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied("This listing is pending admin verification.")

        if ad.author_id == request.user.id:
            return Response(
                {"error": "നിങ്ങളുടെ സ്വന്തം പരസ്യമാണ് ഇത് (You cannot chat with yourself)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        conv = Conversation.get_or_create_between(request.user, ad.author)
        return Response({
            "conversation_id": conv.id,
            "seller_id": ad.author.id,
            "seller_name": ad.author.full_name,
            "ad_title": ad.title,
            "chat_url": f"/chat/{ad.author.id}/"
        }, status=status.HTTP_200_OK)


class JobListingViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for Village Job Openings and Local Employment.
    """
    queryset = JobListing.objects.all().select_related('employer', 'area')
    serializer_class = JobListingSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'company_name', 'description', 'requirements', 'location', 'salary_range']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = JobListing.objects.all().select_related('employer', 'area')

        # Public visitors only see approved & active jobs; employers see their own listings
        if not user.is_authenticated or (not user.is_staff and user.role != User.Role.SUPER_ADMIN):
            if user.is_authenticated:
                qs = qs.filter(Q(is_approved=True, is_active=True) | Q(employer=user))
            else:
                qs = qs.filter(is_approved=True, is_active=True)

        category = self.request.query_params.get('category')
        job_type = self.request.query_params.get('job_type')
        area = self.request.query_params.get('area')
        ward = self.request.query_params.get('ward')
        is_active = self.request.query_params.get('is_active')

        if category:
            qs = qs.filter(category=category)
        if job_type:
            qs = qs.filter(job_type=job_type)
        if area:
            qs = qs.filter(area_id=area)
        if ward:
            qs = qs.filter(ward_number=ward)
        if is_active is not None and (user.is_staff or user.role == User.Role.SUPER_ADMIN):
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        is_approved = user.is_staff or user.role == User.Role.SUPER_ADMIN
        serializer.save(employer=user, is_approved=is_approved)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if instance.employer != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only edit your own job listings.")
        is_approved = instance.is_approved
        if not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            is_approved = False
        serializer.save(is_approved=is_approved)

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.employer != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete your own job listings.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_job(self, request, pk=None):
        if not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Admin permission required to approve job listings.")
        job = self.get_object()
        job.is_approved = True
        job.save(update_fields=['is_approved'])
        return Response({"message": f"Job listing '{job.title}' approved."})

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        job = self.get_object()
        if job.employer != request.user and not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only the employer can toggle hiring status.")
        job.is_active = not job.is_active
        job.save(update_fields=['is_active'])
        return Response({"status": "updated", "is_active": job.is_active})

    @action(detail=True, methods=['post'], url_path='contact-employer')
    def contact_employer(self, request, pk=None):
        job = self.get_object()
        if job.employer_id == request.user.id:
            return Response(
                {"error": "You cannot message yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )
        conv = Conversation.get_or_create_between(request.user, job.employer)
        return Response({
            "conversation_id": conv.id,
            "employer_id": job.employer.id,
            "employer_name": job.employer.full_name,
            "job_title": job.title,
            "chat_url": f"/chat/{job.employer.id}/"
        }, status=status.HTTP_200_OK)


class JobApplicationViewSet(viewsets.ModelViewSet):
    """
    Handles candidate application submission, employer review, and status tracking.
    """
    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = JobApplication.objects.all().select_related('job', 'applicant', 'job__employer')

        if user.is_staff or user.role == User.Role.SUPER_ADMIN:
            pass  # Admins can see all applications
        else:
            # Applicants see their own applications; Employers see applications for their jobs
            qs = qs.filter(Q(applicant=user) | Q(job__employer=user))

        job_id = self.request.query_params.get('job')
        status_filter = self.request.query_params.get('status')
        if job_id:
            qs = qs.filter(job_id=job_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        job = serializer.validated_data.get('job')

        if job.employer == user:
            raise PermissionDenied("You cannot apply to your own job listing.")

        if not job.is_active or not job.is_approved:
            raise ValidationError("This job is currently not accepting applications.")

        if JobApplication.objects.filter(job=job, applicant=user).exists():
            raise ValidationError("You have already applied for this job.")

        application = serializer.save(applicant=user, status=JobApplication.Status.SUBMITTED)

        # Notify employer via in-app notification
        SocialNotification.create_notification(
            recipient=job.employer,
            actor=user,
            ntype=SocialNotification.Type.SYSTEM_ALERT,
            title="പുതിയ തൊഴിൽ അപേക്ഷ (New Job Application)",
            body=f"{user.full_name} '{job.title}' തസ്തികയിലേക്ക് അപേക്ഷ സമർപ്പിച്ചു.",
            link_url=f"/jobs/{job.id}/applications/"
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        # Only employer or admin can update application status and notes
        if instance.job.employer != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only the employer can update application status or remarks.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if instance.applicant != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only withdraw/delete your own application.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """
        Allows employer to advance candidate status: reviewed, shortlisted, accepted, rejected.
        """
        application = self.get_object()
        user = request.user

        if application.job.employer != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only the employer can update candidate status.")

        new_status = request.data.get('status')
        employer_notes = request.data.get('employer_notes', '')

        if new_status:
            if new_status not in JobApplication.Status.values:
                return Response(
                    {"error": f"Invalid status. Choose from: {list(JobApplication.Status.values)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            application.status = new_status

        if employer_notes:
            application.employer_notes = employer_notes

        application.save()

        # Send notification to applicant
        SocialNotification.create_notification(
            recipient=application.applicant,
            actor=user,
            ntype=SocialNotification.Type.SYSTEM_ALERT,
            title=f"തൊഴിൽ അപേക്ഷ അപ്ഡേറ്റ്: {application.job.title}",
            body=f"സ്റ്റാറ്റസ്: {application.get_status_display()}. {employer_notes[:80] if employer_notes else ''}",
            link_url=f"/jobs/applications/{application.id}/"
        )

        return Response(JobApplicationSerializer(application, context={'request': request}).data)
