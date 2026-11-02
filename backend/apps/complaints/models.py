from django.db import models
from django.conf import settings
from apps.accounts.models import Area

class Complaint(models.Model):
    class Category(models.TextChoices):
        WASTE = 'waste', 'മാലിന്യ പ്രശ്നം (Waste Management)'
        ROADS = 'roads', 'റോഡ് / വഴി തടസ്സം (Roads & Pathways)'
        WATER = 'water', 'കുടിവെള്ളം (Drinking Water)'
        ELECTRICITY = 'electricity', 'സ്ട്രീറ്റ് ലൈറ്റ് / വൈദ്യുതി (Streetlights & Power)'
        HEALTH = 'health', 'ശുചിത്വം & ആരോഗ്യം (Public Health)'
        DEVELOPMENT = 'development', 'വികസന നിർദ്ദേശം (Development Suggestion)'
        OTHER = 'other', 'മറ്റുള്ളവ (Other Issues)'

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'സമർപ്പിച്ചു (Submitted)'
        UNDER_REVIEW = 'under_review', 'പരിഗണനയിൽ (Under Review)'
        IN_PROGRESS = 'in_progress', 'നടപടി സ്വീകരിക്കുന്നു (In Progress)'
        RESOLVED = 'resolved', 'പരിഹരിച്ചു (Resolved)'
        REJECTED = 'rejected', 'തള്ളി (Rejected)'

    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='complaints',
        verbose_name="സമർപ്പിച്ച ആൾ"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
        verbose_name="പ്രദേശം (Area)"
    )
    title = models.CharField(max_length=200, verbose_name="വിഷയം (Subject)")
    description = models.TextField(verbose_name="വിശദവിവരങ്ങൾ (Description)")
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
        verbose_name="വിഭാഗം (Category)"
    )
    ward_number = models.PositiveSmallIntegerField(verbose_name="വാർഡ് നമ്പർ")
    location_details = models.CharField(max_length=255, blank=True, verbose_name="കൃത്യമായ സ്ഥലം (Landmark/Location)")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="ലൊക്കേഷൻ അക്ഷാംശം (Latitude)")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="ലൊക്കേഷൻ രേഖാംശം (Longitude)")
    photo = models.ImageField(upload_to='complaints/', null=True, blank=True, verbose_name="ഫോട്ടോ")
    is_anonymous = models.BooleanField(default=False, verbose_name="പേര് രഹസ്യമായി വെക്കുക (Anonymous)")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        verbose_name="സ്റ്റാറ്റസ് (Status)"
    )
    admin_remarks = models.TextField(blank=True, verbose_name="അഡ്മിൻ / വാർഡ് മെമ്പറുടെ മറുപടി (Official Remarks)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "പരാതി / നിർദ്ദേശം (Complaint / Suggestion)"
        verbose_name_plural = "പരാതികളും നിർദ്ദേശങ്ങളും (Complaints & Suggestions)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (വാർഡ് {self.ward_number}) - {self.get_status_display()}"
