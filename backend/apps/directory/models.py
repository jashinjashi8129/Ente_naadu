from django.db import models
from django.conf import settings
from apps.accounts.models import Area

class DirectoryEntry(models.Model):
    """
    Local Services Directory (Electrician, Plumber, Taxi/Auto, Ambulance, Panchayat).
    Single-tap calling for residents.
    """
    class Category(models.TextChoices):
        ELECTRICIAN = 'electrician', 'ഇലക്ട്രീഷ്യൻ (Electrician)'
        PLUMBER = 'plumber', 'പ്ലംബർ (Plumber)'
        TAXI_AUTO = 'taxi_auto', 'ഓട്ടോ / ടാക്സി (Auto / Taxi)'
        DOCTOR_CLINIC = 'doctor', 'ഡോക്ടർ / ക്ലിനിക്ക് (Doctor & Clinic)'
        AMBULANCE = 'ambulance', 'ആംബുലൻസ് (Ambulance - 24/7)'
        GOVERNMENT_OFFICE = 'government', 'പഞ്ചായത്ത് / വില്ലേജ് ഓഫീസ് (Government Office)'
        POLICE_FIRE = 'police_fire', 'പോലീസ് / ഫയർഫോഴ്സ് (Police / Fire)'
        OTHER = 'other', 'മറ്റ് അവശ്യ സേവനങ്ങൾ (Other Services)'

    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='directory_entries',
        verbose_name="പ്രദേശം"
    )
    name = models.CharField(max_length=200, verbose_name="സേവന ദാതാവിന്റെ പേര് / സ്ഥാപനം")
    category = models.CharField(max_length=30, choices=Category.choices, verbose_name="വിഭാഗം")
    phone_number = models.CharField(max_length=17, verbose_name="പ്രധാന ഫോൺ നമ്പർ")
    secondary_phone = models.CharField(max_length=17, blank=True, verbose_name="മറ്റൊരു നമ്പർ (ഓപ്ഷണൽ)")
    address_or_stand = models.CharField(max_length=255, verbose_name="സ്റ്റാൻഡ് / വിലാസം")
    ward_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="വാർഡ് നമ്പർ")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_directory_entries',
        verbose_name="സമർപ്പിച്ച ഉപയോക്താവ്"
    )
    is_emergency_service = models.BooleanField(default=False, verbose_name="അടിയന്തര സേവനം (Emergency)")
    is_verified = models.BooleanField(default=False, verbose_name="പരിശോധിച്ച നമ്പർ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "സേവന ഡയറക്ടറി (Directory Entry)"
        verbose_name_plural = "പ്രാദേശിക സേവന ഡയറക്ടറി (Services Directory)"
        ordering = ['-is_emergency_service', 'category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()}) - {self.phone_number}"

class BloodDonor(models.Model):
    """
    Voluntary Blood Donors list with easy blood-group search.
    """
    class BloodGroup(models.TextChoices):
        A_POS = 'A+', 'A Positive (A+)'
        A_NEG = 'A-', 'A Negative (A-)'
        B_POS = 'B+', 'B Positive (B+)'
        B_NEG = 'B-', 'B Negative (B-)'
        O_POS = 'O+', 'O Positive (O+)'
        O_NEG = 'O-', 'O Negative (O-)'
        AB_POS = 'AB+', 'AB Positive (AB+)'
        AB_NEG = 'AB-', 'AB Negative (AB-)'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='blood_donor_profile',
        verbose_name="രജിസ്റ്റർ ചെയ്ത യൂസർ"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blood_donors',
        verbose_name="പ്രദേശം"
    )
    name = models.CharField(max_length=150, verbose_name="ദാതാവിന്റെ പേര്")
    blood_group = models.CharField(max_length=5, choices=BloodGroup.choices, verbose_name="രക്തഗ്രൂപ്പ്")
    phone_number = models.CharField(max_length=17, verbose_name="ഫോൺ നമ്പർ")
    ward_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="വാർഡ് നമ്പർ")
    is_available = models.BooleanField(default=True, verbose_name="രക്തം നൽകാൻ ഇപ്പോൾ തയ്യാറാണോ")
    last_donated_date = models.DateField(null=True, blank=True, verbose_name="അവസാനം ദാനം ചെയ്ത തീയതി")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "രക്തദാതാവ് (Blood Donor)"
        verbose_name_plural = "രക്തദാതാക്കളുടെ പട്ടിക (Blood Donors)"
        ordering = ['blood_group', 'name']

    def __str__(self):
        return f"{self.name} ({self.blood_group}) - {self.phone_number}"

class ClassifiedAd(models.Model):
    """
    Community Classifieds Notice Board (Rent, Sale, Job Vacancies).
    Subject to Admin verification.
    """
    class AdType(models.TextChoices):
        RENT = 'rent', 'വാടകയ്ക്ക് (House / Shop for Rent)'
        SALE = 'sale', 'വിൽപനയ്ക്ക് (Vehicle / Land / Items for Sale)'
        JOB = 'job', 'തൊഴിൽ ഒഴിവ് (Job Vacancy / Hiring)'
        OTHER = 'other', 'മറ്റുള്ളവ (General Classified)'

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classified_ads',
        verbose_name="പരസ്യം നൽകിയ ആൾ"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classified_ads',
        verbose_name="പ്രദേശം"
    )
    ad_type = models.CharField(max_length=20, choices=AdType.choices, verbose_name="വിഭാഗം")
    title = models.CharField(max_length=200, verbose_name="തലക്കെട്ട്")
    description = models.TextField(verbose_name="വിശദവിവരങ്ങൾ")
    price_or_salary = models.CharField(max_length=100, blank=True, verbose_name="വില / ശമ്പളം / വാടക")
    condition = models.CharField(
        max_length=30,
        blank=True,
        default='used',
        choices=[
            ('new', 'പുതിയത് (Brand New)'),
            ('like_new', 'വളരെ നല്ല അവസ്ഥ (Like New)'),
            ('used', 'ഉപയോഗിച്ചത് (Gently Used)'),
            ('for_parts', 'പാർട്സുകൾക്കായി (For Parts)')
        ],
        verbose_name="അവസ്ഥ (Condition)"
    )
    location = models.CharField(max_length=200, blank=True, verbose_name="സ്ഥലം (Location / Landmark)")
    contact_phone = models.CharField(max_length=17, verbose_name="ബന്ധപ്പെടേണ്ട ഫോൺ നമ്പർ")
    photo = models.ImageField(upload_to='classifieds/', null=True, blank=True)
    is_approved = models.BooleanField(default=False, verbose_name="അഡ്മിൻ അനുമതി നൽകിയത്")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ക്ലാസിഫൈഡ് പരസ്യം (Classified Ad)"
        verbose_name_plural = "വാടക / വിൽപന / തൊഴിൽ ബോർഡ് (Notice Board)"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_ad_type_display()}] {self.title}"


class JobListing(models.Model):
    """
    Local Employment Opportunities & Hiring notice board.
    Employers and small business owners post local job openings with clear wages, hours, and expectations.
    """
    class JobType(models.TextChoices):
        FULL_TIME = 'full_time', 'മുഴുസമയ ജോലി (Full Time)'
        PART_TIME = 'part_time', 'ഭാഗിക സമയ ജോലി (Part Time)'
        DAILY_WAGE = 'daily_wage', 'ദിവസ വേതനം (Daily Wage)'
        CONTRACT = 'contract', 'കരാർ ജോലി (Contract)'

    class JobCategory(models.TextChoices):
        DRIVER = 'driver', 'ഡ്രൈവർ (Driver)'
        SALES = 'sales', 'സെയിൽസ് / കടകൾ (Sales / Retail)'
        OFFICE = 'office', 'ഓഫീസ് / ക്ലർക്ക് (Office / Clerk)'
        COOK = 'cook', 'പാചകം / കാറ്ററിംഗ് (Cook / Catering)'
        CONSTRUCTION = 'construction', 'നിർമ്മാണം / പണിക്കാർ (Construction & Labor)'
        CLEANER = 'cleaner', 'ഹൗസ് കീപ്പിംഗ് (Housekeeping / Cleaning)'
        SECURITY = 'security', 'സെക്യൂരിറ്റി (Security Guard)'
        TECHNICIAN = 'technician', 'ടെക്നീഷ്യൻ / ഇലക്ട്രിക്കൽ (Technician)'
        OTHER = 'other', 'മറ്റുള്ളവ (Other Jobs)'

    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_listings',
        verbose_name="തൊഴിൽ നൽകുന്നയാൾ (Employer)"
    )
    company_name = models.CharField(max_length=200, verbose_name="സ്ഥാപനം / തൊഴിൽ ദാതാവ് (Company Name)")
    employer_bio = models.TextField(blank=True, verbose_name="തൊഴിൽ ദാതാവിന്റെ വിവരങ്ങൾ (Employer Bio)")
    title = models.CharField(max_length=200, verbose_name="തൊഴിൽ തസ്തിക (Job Title)")
    category = models.CharField(
        max_length=30,
        choices=JobCategory.choices,
        default=JobCategory.OTHER,
        verbose_name="വിഭാഗം (Category)"
    )
    job_type = models.CharField(
        max_length=20,
        choices=JobType.choices,
        default=JobType.FULL_TIME,
        verbose_name="തൊഴിൽ രീതി (Job Type)"
    )
    description = models.TextField(verbose_name="വിശദവിവരങ്ങൾ (Description)")
    requirements = models.TextField(blank=True, verbose_name="യോഗ്യതകൾ / നിബന്ധനകൾ (Requirements)")
    salary_range = models.CharField(max_length=100, blank=True, verbose_name="ശമ്പളം / വേതനം (Salary / Wage)")
    location = models.CharField(max_length=200, verbose_name="ജോലി സ്ഥലം (Job Location / Landmark)")
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_listings',
        verbose_name="പ്രദേശം (Area)"
    )
    ward_number = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="വാർഡ് നമ്പർ (Ward)")
    contact_phone = models.CharField(max_length=17, verbose_name="ബന്ധപ്പെടേണ്ട ഫോൺ നമ്പർ")
    is_active = models.BooleanField(default=True, verbose_name="സജീവം (Active / Hiring Open)")
    is_approved = models.BooleanField(default=False, verbose_name="അഡ്മിൻ അനുമതി നൽകിയത് (Admin Approved)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "തൊഴിൽ ഒഴിവ് (Job Listing)"
        verbose_name_plural = "തൊഴിൽ ഒഴിവുകൾ (Job Listings)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} @ {self.company_name}"


class JobApplication(models.Model):
    """
    Direct in-app job applications submitted by authenticated village residents.
    Allows applicants to submit details and track their application status transparently.
    """
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'സമർപ്പിച്ചു (Submitted)'
        REVIEWED = 'reviewed', 'പരിശോധിച്ചു (Under Review)'
        SHORTLISTED = 'shortlisted', 'ഷോർട്ട് ലിസ്റ്റ് ചെയ്തു (Shortlisted)'
        ACCEPTED = 'accepted', 'തിരഞ്ഞെടുത്തു (Hired / Accepted)'
        REJECTED = 'rejected', 'നിരസിച്ചു (Rejected)'

    job = models.ForeignKey(
        JobListing,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name="തൊഴിൽ (Job Listing)"
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_applications',
        verbose_name="അപേക്ഷകൻ (Applicant)"
    )
    full_name = models.CharField(max_length=150, verbose_name="അപേക്ഷകന്റെ പേര്")
    contact_phone = models.CharField(max_length=17, verbose_name="ബന്ധപ്പെടേണ്ട ഫോൺ നമ്പർ")
    experience_summary = models.TextField(verbose_name="മുൻപരിചയവും യോഗ്യതയും (Experience Summary)")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        verbose_name="സ്റ്റാറ്റസ് (Application Status)"
    )
    employer_notes = models.TextField(blank=True, verbose_name="തൊഴിൽ ദാതാവിന്റെ മറുപടി / കുറിപ്പ് (Employer Feedback)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "തൊഴിൽ അപേക്ഷ (Job Application)"
        verbose_name_plural = "തൊഴിൽ അപേക്ഷകൾ (Job Applications)"
        ordering = ['-created_at']
        unique_together = ('job', 'applicant')

    def __str__(self):
        return f"{self.full_name} -> {self.job.title} ({self.get_status_display()})"
