from rest_framework import serializers
from .models import DirectoryEntry, BloodDonor, ClassifiedAd, JobListing, JobApplication

class DirectoryEntrySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = DirectoryEntry
        fields = [
            'id',
            'area',
            'name',
            'category',
            'category_display',
            'phone_number',
            'secondary_phone',
            'address_or_stand',
            'ward_number',
            'is_emergency_service',
            'is_verified',
            'submitted_by',
            'submitted_by_name',
            'created_at'
        ]
        read_only_fields = ['id', 'submitted_by', 'submitted_by_name', 'is_verified', 'created_at']

class BloodDonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodDonor
        fields = [
            'id',
            'user',
            'area',
            'name',
            'blood_group',
            'phone_number',
            'ward_number',
            'is_available',
            'last_donated_date',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']

class ClassifiedAdSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    seller_name = serializers.CharField(source='author.full_name', read_only=True)
    seller_id = serializers.IntegerField(source='author.id', read_only=True)
    seller_chat_url = serializers.SerializerMethodField()
    ad_type_display = serializers.CharField(source='get_ad_type_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)

    class Meta:
        model = ClassifiedAd
        fields = [
            'id',
            'author',
            'author_name',
            'seller_id',
            'seller_name',
            'seller_chat_url',
            'area',
            'ad_type',
            'ad_type_display',
            'title',
            'description',
            'condition',
            'condition_display',
            'location',
            'price_or_salary',
            'contact_phone',
            'photo',
            'is_approved',
            'created_at'
        ]
        read_only_fields = ['id', 'author', 'author_name', 'seller_id', 'seller_name', 'seller_chat_url', 'is_approved', 'created_at']

    def get_seller_chat_url(self, obj):
        if obj.author_id:
            return f"/chat/{obj.author_id}/"
        return None


class JobListingSerializer(serializers.ModelSerializer):
    employer_name = serializers.CharField(source='employer.full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    job_type_display = serializers.CharField(source='get_job_type_display', read_only=True)
    applications_count = serializers.SerializerMethodField()
    employer_chat_url = serializers.SerializerMethodField()

    class Meta:
        model = JobListing
        fields = [
            'id',
            'employer',
            'employer_name',
            'employer_chat_url',
            'company_name',
            'employer_bio',
            'title',
            'category',
            'category_display',
            'job_type',
            'job_type_display',
            'description',
            'requirements',
            'salary_range',
            'location',
            'area',
            'ward_number',
            'contact_phone',
            'is_active',
            'is_approved',
            'applications_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'employer',
            'employer_name',
            'employer_chat_url',
            'is_approved',
            'applications_count',
            'created_at',
            'updated_at'
        ]

    def get_applications_count(self, obj):
        request = self.context.get('request')
        if request and (request.user.is_staff or (request.user.is_authenticated and obj.employer_id == request.user.id)):
            return obj.applications.count()
        return None

    def get_employer_chat_url(self, obj):
        if obj.employer_id:
            return f"/chat/{obj.employer_id}/"
        return None


class JobApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.company_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    applicant_name = serializers.CharField(source='applicant.full_name', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id',
            'job',
            'job_title',
            'company_name',
            'applicant',
            'applicant_name',
            'full_name',
            'contact_phone',
            'experience_summary',
            'status',
            'status_display',
            'employer_notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'applicant',
            'applicant_name',
            'job_title',
            'company_name',
            'status',
            'status_display',
            'employer_notes',
            'created_at',
            'updated_at'
        ]

