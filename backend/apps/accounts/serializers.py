from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Area, AuditLog, UserLocation, UserReport
from apps.common.geo import is_valid_coord

class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ['id', 'name', 'district', 'state', 'pincode', 'is_active']

class UserSerializer(serializers.ModelSerializer):
    area_name = serializers.CharField(source='area.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'phone_number',
            'full_name',
            'role',
            'area',
            'area_name',
            'ward_number',
            'address',
            'profile_photo',
            'is_blocked',
            'created_at'
        ]
        read_only_fields = ['id', 'phone_number', 'role', 'is_blocked', 'created_at']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(
        choices=[User.Role.CITIZEN, User.Role.SHOP_OWNER],
        default=User.Role.CITIZEN,
        required=False
    )

    class Meta:
        model = User
        fields = [
            'id',
            'phone_number',
            'full_name',
            'password',
            'role',
            'area',
            'ward_number',
            'address'
        ]

    def validate_role(self, value):
        if value not in [User.Role.CITIZEN, User.Role.SHOP_OWNER]:
            raise serializers.ValidationError("Invalid role. Public registration only allows Citizen or Shop Owner.")
        return value

    def create(self, validated_data):
        role = validated_data.get('role', User.Role.CITIZEN)
        if role not in [User.Role.CITIZEN, User.Role.SHOP_OWNER]:
            validated_data['role'] = User.Role.CITIZEN
        return User.objects.create_user(**validated_data)

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get('phone_number', '').strip().replace(" ", "")
        password = data.get('password')

        if not phone_number or not password:
            raise serializers.ValidationError("Phone number and password are required.")

        user = authenticate(username=phone_number, password=password)
        if not user:
            raise serializers.ValidationError("Invalid phone number or password.")

        if user.is_blocked:
            reason = user.block_reason or "Violation of community guidelines."
            raise serializers.ValidationError(f"Your account has been blocked: {reason}")

        if not user.is_active:
            raise serializers.ValidationError("User account is inactive. Please contact the administrator.")

        data['user'] = user
        return data

class AdminResetPasswordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    new_password = serializers.CharField(min_length=6)
    reason = serializers.CharField(required=False, default="Requested password reset")

class BlockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    reason = serializers.CharField(min_length=5)
    block = serializers.BooleanField(default=True)

class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'performed_by',
            'performed_by_name',
            'action',
            'action_display',
            'target_type',
            'target_id',
            'target_identifier',
            'reason',
            'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class UserLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLocation
        fields = [
            'latitude',
            'longitude',
            'is_sharing_enabled',
            'is_paused',
            'share_precision',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class UserLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate(self, attrs):
        lat = attrs.get('latitude')
        lon = attrs.get('longitude')
        if not is_valid_coord(lat, lon):
            raise serializers.ValidationError(
                "Invalid GPS coordinates. Latitude must be in [-90, 90] and Longitude in [-180, 180]."
            )
        return attrs


class LocationPreferencesSerializer(serializers.Serializer):
    is_sharing_enabled = serializers.BooleanField(required=False)
    is_paused = serializers.BooleanField(required=False)
    share_precision = serializers.ChoiceField(
        choices=[UserLocation.Precision.EXACT, UserLocation.Precision.APPROXIMATE],
        required=False
    )


class UserReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.full_name', read_only=True)
    reported_user_name = serializers.CharField(source='reported_user.full_name', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.full_name', read_only=True)

    class Meta:
        model = UserReport
        fields = [
            'id',
            'reporter',
            'reporter_name',
            'reported_user',
            'reported_user_name',
            'content_type',
            'content_id',
            'reason',
            'reason_display',
            'description',
            'status',
            'status_display',
            'admin_action_taken',
            'admin_notes',
            'reviewed_by',
            'reviewed_by_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'reporter',
            'reporter_name',
            'reported_user_name',
            'status',
            'status_display',
            'admin_action_taken',
            'admin_notes',
            'reviewed_by',
            'reviewed_by_name',
            'created_at',
            'updated_at'
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        reported_user = attrs.get('reported_user')
        if request and reported_user and reported_user.id == request.user.id:
            raise serializers.ValidationError("നിങ്ങൾക്ക് സ്വന്തമായി റിപ്പോർട്ട് ചെയ്യാൻ കഴിയില്ല (You cannot report yourself).")
        return attrs

