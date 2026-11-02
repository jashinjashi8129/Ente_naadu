from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.conf import settings

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

class Area(models.Model):
    """
    Geographic community division (Panchayat, Municipality, Ward clusters).
    Allows Ente Naadu to expand seamlessly to neighboring villages.
    """
    name = models.CharField(max_length=150, unique=True, verbose_name="പ്രദേശത്തിന്റെ പേര് (Area/Panchayat)")
    district = models.CharField(max_length=100, default="Thiruvananthapuram", verbose_name="ജില്ല (District)")
    state = models.CharField(max_length=100, default="Kerala", verbose_name="സംസ്ഥാനം (State)")
    pincode = models.CharField(max_length=10, blank=True, verbose_name="പിൻകോഡ് (Pincode)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "പ്രദേശം / പഞ്ചായത്ത് (Area)"
        verbose_name_plural = "പ്രദേശങ്ങൾ (Areas)"
        ordering = ['name']

    def __str__(self):
        return f"{self.name}, {self.district}"

class UserManager(BaseUserManager):
    """Custom manager for User with phone_number as unique username."""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number must be provided')
        phone_number = phone_number.strip().replace(" ", "")
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.SUPER_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for Ente Naadu.
    Uses Phone Number as the primary identifier to eliminate costly SMS OTPs.
    """
    class Role(models.TextChoices):
        CITIZEN = 'citizen', 'നാട്ടുകാരൻ (Citizen)'
        SHOP_OWNER = 'shop_owner', 'വ്യാപാരി (Shop Owner)'
        WARD_ADMIN = 'ward_admin', 'വാർഡ് പ്രതിനിധി (Ward Representative)'
        SUPER_ADMIN = 'super_admin', 'പ്രധാന അഡ്മിൻ (Super Admin)'

    phone_number = models.CharField(
        max_length=17,
        unique=True,
        validators=[phone_regex],
        verbose_name="ഫോൺ നമ്പർ (Phone Number)"
    )
    full_name = models.CharField(max_length=150, verbose_name="പൂർണ്ണ നാമം (Full Name)")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
        verbose_name="റോൾ (Role)"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name="പ്രദേശം (Area)"
    )
    ward_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="വാർഡ് നമ്പർ (Ward Number)"
    )
    address = models.TextField(blank=True, verbose_name="മേൽവിലാസം (Address)")
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)

    # Moderation & Account Suspension
    is_blocked = models.BooleanField(
        default=False,
        verbose_name="ബ്ലോക്ക് ചെയ്തിട്ടുണ്ടോ (Is Blocked)"
    )
    block_reason = models.TextField(
        blank=True,
        verbose_name="ബ്ലോക്ക് ചെയ്യാനുള്ള കാരണം (Block Reason)"
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = "യൂസർ (User)"
        verbose_name_plural = "യൂസർമാർ (Users)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

class AuditLog(models.Model):
    """
    Audit log tracking all critical administrative actions (blocks, approvals, content deletions).
    """
    class Action(models.TextChoices):
        BLOCK_USER = 'block_user', 'യൂസറെ ബ്ലോക്ക് ചെയ്തു'
        UNBLOCK_USER = 'unblock_user', 'യൂസറുടെ ബ്ലോക്ക് നീക്കി'
        APPROVE_SHOP = 'approve_shop', 'കട അപ്രൂവ് ചെയ്തു'
        REJECT_SHOP = 'reject_shop', 'കട നിരസിച്ചു'
        REMOVE_CONTENT = 'remove_content', 'ഉള്ളടക്കം നീക്കം ചെയ്തു'
        RESET_PASSWORD = 'reset_password', 'പാസ്‌വേഡ് റീസെറ്റ് ചെയ്തു'
        PRODUCT_CREATE = 'product_create', 'ഉൽപ്പന്നം ചേർത്തു'
        PRODUCT_UPDATE = 'product_update', 'ഉൽപ്പന്നം പുതുക്കി'
        PRODUCT_DELETE = 'product_delete', 'ഉൽപ്പന്നം നീക്കം ചെയ്തു'
        PRODUCT_STOCK_TOGGLE = 'product_stock_toggle', 'സ്റ്റോക്ക് മാറ്റി'
        ORDER_STATUS_UPDATE = 'order_status_update', 'ഓർഡർ സ്റ്റാറ്റസ് മാറ്റി'
        ORDER_CANCEL = 'order_cancel', 'ഓർഡർ റദ്ദാക്കി'
        BOOKING_STATUS_UPDATE = 'booking_status_update', 'ബുക്കിംഗ് സ്റ്റാറ്റസ് മാറ്റി'
        BOOKING_CANCEL = 'booking_cancel', 'ബുക്കിംഗ് റദ്ദാക്കി'
        DIRECTORY_APPROVE = 'directory_approve', 'ഡയറക്ടറി അപ്രൂവ് ചെയ്തു'
        DIRECTORY_REJECT = 'directory_reject', 'ഡയറക്ടറി നിരസിച്ചു'
        COMPLAINT_RESOLVE = 'complaint_resolve', 'പരാതി പരിഹരിച്ചു'
        REPORT_RESOLVE = 'report_resolve', 'റിപ്പോർട്ടിൽ നടപടി സ്വീകരിച്ചു'
        REPORT_DISMISS = 'report_dismiss', 'റിപ്പോർട്ട് തള്ളി'
        CLASSIFIED_APPROVE = 'classified_approve', 'ക്ലാസിഫൈഡ് അപ്രൂവ് ചെയ്തു'
        JOB_APPROVE = 'job_approve', 'തൊഴിൽ പരസ്യം അപ്രൂവ് ചെയ്തു'

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_actions',
        verbose_name="നടപടി എടുത്ത അഡ്മിൻ"
    )
    action = models.CharField(max_length=50, choices=Action.choices, verbose_name="നടപടി")
    target_type = models.CharField(max_length=100, verbose_name="ടാർഗെറ്റ് മോഡൽ (User/Shop/Content)")
    target_id = models.IntegerField(verbose_name="ടാർഗെറ്റ് ഐഡി")
    target_identifier = models.CharField(max_length=200, blank=True, verbose_name="ടാർഗെറ്റ് പേര്/നമ്പർ")
    reason = models.TextField(verbose_name="കാരണം (Reason)")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ഓഡിറ്റ് ലോഗ് (Audit Log)"
        verbose_name_plural = "ഓഡിറ്റ് ലോഗുകൾ (Audit Logs)"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} - {self.target_identifier} ({self.timestamp:%Y-%m-%d %H:%M})"


class UserLocation(models.Model):
    """
    Stores GPS location and privacy controls for authenticated citizens.
    Privacy first: Location sharing is disabled by default and requires explicit user consent.
    Stale coordinates (> 24 hours) automatically expire to prevent tracking.
    """
    class Precision(models.TextChoices):
        EXACT = 'exact', 'കൃത്യമായ സ്ഥലം (Exact)'
        APPROXIMATE = 'approximate', 'ഏകദേശ സ്ഥലം (Approximate ~500m)'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='location',
        verbose_name="ഉപയോക്താവ് (User)"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)

    is_sharing_enabled = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="സുഹൃത്തുക്കളുമായി ലൊക്കേഷൻ പങ്കിടുക (Share with Friends)"
    )
    is_paused = models.BooleanField(
        default=False,
        verbose_name="താല്കാലികമായി നിർത്തുക (Pause Sharing)"
    )
    share_precision = models.CharField(
        max_length=20,
        choices=Precision.choices,
        default=Precision.EXACT,
        verbose_name="ലൊക്കേഷൻ കൃത്യത (Location Precision)"
    )
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "ഉപയോക്തൃ ലൊക്കേഷൻ (User Location)"
        verbose_name_plural = "ഉപയോക്തൃ ലൊക്കേഷനുകൾ (User Locations)"

    def __str__(self):
        return f"{self.user.full_name}: ({self.latitude}, {self.longitude}) - Sharing: {self.is_sharing_enabled}"

    def is_stale(self, max_hours=24):
        """Returns True if location update is older than max_hours."""
        from django.utils import timezone
        import datetime
        if not self.updated_at:
            return True
        return timezone.now() - self.updated_at > datetime.timedelta(hours=max_hours)

    def is_visible_to_friends(self):
        """Checks if current state allows sharing with accepted friends."""
        if not self.is_sharing_enabled or self.is_paused:
            return False
        if not self.latitude or not self.longitude:
            return False
        if self.is_stale(max_hours=24):
            return False
        return True

    def get_coordinates(self):
        """
        Returns (lat, lon) respecting user's precision setting.
        If approximate, safely rounds to 2 decimals (~1km resolution) to preserve privacy.
        """
        if not self.latitude or not self.longitude:
            return None, None
        lat = float(self.latitude)
        lon = float(self.longitude)
        if self.share_precision == self.Precision.APPROXIMATE:
            return round(lat, 2), round(lon, 2)
        return lat, lon


class UserReport(models.Model):
    """
    Community trust and moderation model for reporting spam, harassment, fake profiles, and abuse.
    Reports are securely submitted by authenticated residents and handled by authorized admins/staff.
    """
    class Reason(models.TextChoices):
        SPAM = 'spam', 'സ്പാം / പരസ്യ ശല്യം (Spam & Advertising)'
        ABUSE = 'abuse', 'അസഭ്യം / ഭീഷണി (Abuse & Harassment)'
        FRAUD = 'fraud', 'തട്ടിപ്പ് / വ്യാജം (Fraud & Scam)'
        MISINFORMATION = 'misinformation', 'വ്യാജ വാർത്ത (Misinformation)'
        OFFENSIVE = 'offensive', 'മോശമായ ഉള്ളടക്കം (Inappropriate Content)'
        OTHER = 'other', 'മറ്റുള്ളവ (Other Violation)'

    class Status(models.TextChoices):
        PENDING = 'pending', 'പരിഗണനയിൽ (Pending Review)'
        INVESTIGATING = 'investigating', 'അന്വേഷണത്തിൽ (Investigating)'
        RESOLVED = 'resolved', 'നടപടി സ്വീകരിച്ചു (Resolved - Action Taken)'
        DISMISSED = 'dismissed', 'തള്ളി (Dismissed - No Violation)'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='filed_reports',
        verbose_name="പരാതിപ്പെട്ടയാൾ (Reporter)"
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_reports',
        verbose_name="ആരോപണവിധേയൻ (Reported User)"
    )
    content_type = models.CharField(
        max_length=50,
        default='user',
        verbose_name="ഉള്ളടക്ക തരം (Target Type: user, shop, classified, job, message)"
    )
    content_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="ഉള്ളടക്ക ഐഡി (Target Content ID)"
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
        default=Reason.SPAM,
        verbose_name="കാരണം (Reason)"
    )
    description = models.TextField(
        blank=True,
        verbose_name="വിശദവിവരങ്ങൾ (Detailed Description)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="സ്റ്റാറ്റസ് (Status)"
    )
    admin_action_taken = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="സ്വീകരിച്ച നടപടി (Admin Action)"
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name="അഡ്മിൻ കുറിപ്പുകൾ (Staff Notes)"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports',
        verbose_name="പരിശോധിച്ച അഡ്മിൻ"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ദുരുപയോഗ റിപ്പോർട്ട് (Abuse Report)"
        verbose_name_plural = "ദുരുപയോഗ റിപ്പോർട്ടുകൾ (Abuse Reports)"
        ordering = ['-created_at']

    def __str__(self):
        return f"Report #{self.id} [{self.get_reason_display()}] by {self.reporter.full_name}"


