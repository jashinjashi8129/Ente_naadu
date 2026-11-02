from django.db import models
from django.conf import settings
from apps.accounts.models import Area

class EventNotice(models.Model):
    class NoticeType(models.TextChoices):
        ANNOUNCEMENT = 'announcement', 'പൊതു അറിയിപ്പ് / വാർത്ത (Announcement / News)'
        EVENT = 'event', 'പരിപാടി / സമ്മേളനം (Event / Gathering)'

    class Category(models.TextChoices):
        PANCHAYAT = 'panchayat', 'പഞ്ചായത്ത് നോട്ടീസ് (Panchayat Circular)'
        FESTIVAL = 'festival', 'ആഘോഷം / ഉത്സവം (Festival & Cultural)'
        MEDICAL = 'medical', 'മെഡിക്കൽ ക്യാമ്പ് (Health & Blood Donation)'
        SPORTS = 'sports', 'കായികം / ക്ലബ്ബ് പരിപാടികൾ (Sports & Arts)'
        EMERGENCY = 'emergency', 'അടിയന്തര മുന്നറിയിപ്പ് (Emergency Alert)'
        GENERAL = 'general', 'പൊതു അറിയിപ്പ് (General Announcement)'

    notice_type = models.CharField(
        max_length=20,
        choices=NoticeType.choices,
        default=NoticeType.ANNOUNCEMENT,
        verbose_name="അറിയിപ്പ് തരം (Type)"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        verbose_name="പ്രദേശം (Area)"
    )
    title = models.CharField(max_length=250, verbose_name="തലക്കെട്ട് (Title)")
    description = models.TextField(verbose_name="വിശദവിവരങ്ങൾ (Description)")
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
        verbose_name="വിഭാഗം (Category)"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='posted_events',
        verbose_name="അറിയിപ്പ് നൽകിയ ആൾ"
    )
    ward_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank if applicable to the entire village/panchayat",
        verbose_name="ബാധകമായ വാർഡ്"
    )
    event_date = models.DateTimeField(null=True, blank=True, verbose_name="പരിപാടി നടക്കുന്ന തീയതി/സമയം")
    venue = models.CharField(max_length=200, blank=True, verbose_name="സ്ഥലം (Venue)")
    is_emergency = models.BooleanField(default=False, verbose_name="അടിയന്തര മുന്നറിയിപ്പ് (Urgent Alert)")
    poster_image = models.ImageField(upload_to='events/posters/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "അറിയിപ്പ് / പരിപാടി (Notice / Event)"
        verbose_name_plural = "അറിയിപ്പുകൾ & പരിപാടികൾ (Notices & Events)"
        ordering = ['-is_emergency', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

class EventRSVP(models.Model):
    class Status(models.TextChoices):
        GOING = 'going', 'പങ്കെടുക്കുന്നു (Going)'
        NOT_GOING = 'not_going', 'പങ്കെടുക്കുന്നില്ല (Not Going)'
        MAYBE = 'maybe', 'തീരുമാനിച്ചില്ല (Maybe)'

    event = models.ForeignKey(
        EventNotice,
        on_delete=models.CASCADE,
        related_name='rsvps',
        verbose_name="പരിപാടി"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_rsvps',
        verbose_name="ഉപയോക്താവ്"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.GOING,
        verbose_name="പങ്കാളിത്തം"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "പരിപാടി RSVP"
        verbose_name_plural = "പരിപാടി RSVPs"
        unique_together = ('event', 'user')

    def __str__(self):
        return f"{self.user.full_name} - {self.event.title} ({self.get_status_display()})"
