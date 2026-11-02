from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from apps.accounts.models import Area

class ShopCategory(models.Model):
    class InteractionMode(models.TextChoices):
        ORDER = 'order', 'ഓർഡർ (Order - ഹോട്ടൽ, പലചരക്ക്, ബേക്കറി)'
        BOOKING = 'booking', 'ബുക്കിംഗ് (Booking - ബാർബർ, ബ്യൂട്ടി പാർലർ, അക്ഷയ, ടേബിൾ)'
        REQUEST = 'request', 'റിക്വസ്റ്റ് (Request - റിപ്പയറിംഗ്, ടെയ്‌ലറിംഗ്, മെഡിക്കൽ)'

    class BusinessType(models.TextChoices):
        GENERAL = 'general', 'ജനറൽ സ്റ്റോർ (General Shop)'
        BEAUTY_PARLOUR = 'beauty_parlour', 'ബ്യൂട്ടി പാർലർ / സലൂൺ (Beauty Parlour)'
        MEDICAL = 'medical', 'മെഡിക്കൽ ഷോപ്പ് (Medical Shop)'
        REPAIR = 'repair', 'റിപ്പയർ / സർവീസ് (Repair Shop)'
        RESTAURANT = 'restaurant', 'ഹോട്ടൽ / റസ്റ്റോറന്റ് (Restaurant)'
        OTHER_SERVICE = 'other_service', 'മറ്റു സേവനങ്ങൾ (Other Services)'

    name = models.CharField(max_length=100, unique=True, verbose_name="വിഭാഗം (Category Name)")
    description = models.TextField(blank=True, verbose_name="വിവരണം (Description)")
    icon_name = models.CharField(max_length=50, blank=True, default='store', help_text="Material icon identifier")
    interaction_mode = models.CharField(
        max_length=20,
        choices=InteractionMode.choices,
        default=InteractionMode.ORDER,
        verbose_name="ഇടപാട് രീതി (Interaction Mode)"
    )
    business_type = models.CharField(
        max_length=30,
        choices=BusinessType.choices,
        default=BusinessType.GENERAL,
        verbose_name="സ്ഥാപന തരം (Business Type)"
    )

    class Meta:
        verbose_name = "ഷോപ്പ് വിഭാഗം (Shop Category)"
        verbose_name_plural = "ഷോപ്പ് വിഭാഗങ്ങൾ (Shop Categories)"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_interaction_mode_display()})"


DEFAULT_RATING_CRITERIA = {
    ShopCategory.BusinessType.GENERAL: [
        {'name': 'Product Quality', 'name_ml': 'ഉൽപ്പന്ന ഗുണനിലവാരം', 'slug': 'product_quality', 'order': 1},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 2},
        {'name': 'Packing & Delivery', 'name_ml': 'പാക്കിംഗും ഡെലിവറിയും', 'slug': 'packing_delivery', 'order': 3},
        {'name': 'Customer Service', 'name_ml': 'ഉപഭോക്തൃ സേവനം', 'slug': 'customer_service', 'order': 4},
    ],
    ShopCategory.BusinessType.BEAUTY_PARLOUR: [
        {'name': 'Service Quality', 'name_ml': 'സേവന ഗുണനിലവാരം', 'slug': 'service_quality', 'order': 1},
        {'name': 'Staff Behaviour', 'name_ml': 'ജീവനക്കാരുടെ പെരുമാറ്റം', 'slug': 'staff_behaviour', 'order': 2},
        {'name': 'Cleanliness & Hygiene', 'name_ml': 'ശുചിത്വവും വൃത്തിയും', 'slug': 'cleanliness_hygiene', 'order': 3},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 4},
        {'name': 'Appointment Waiting Time', 'name_ml': 'വെയ്റ്റിംഗ് സമയം', 'slug': 'waiting_time', 'order': 5},
    ],
    ShopCategory.BusinessType.REPAIR: [
        {'name': 'Repair Quality', 'name_ml': 'റിപ്പയറിംഗ് ഗുണനിലവാരം', 'slug': 'repair_quality', 'order': 1},
        {'name': 'Service Time', 'name_ml': 'സർവീസ് സമയം', 'slug': 'service_time', 'order': 2},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 3},
        {'name': 'Customer Support', 'name_ml': 'കസ്റ്റമർ സപ്പോർട്ട്', 'slug': 'customer_support', 'order': 4},
    ],
    ShopCategory.BusinessType.RESTAURANT: [
        {'name': 'Food Quality', 'name_ml': 'ഭക്ഷണ ഗുണനിലവാരം', 'slug': 'food_quality', 'order': 1},
        {'name': 'Taste', 'name_ml': 'രുചി', 'slug': 'taste', 'order': 2},
        {'name': 'Cleanliness', 'name_ml': 'ശുചിത്വം', 'slug': 'cleanliness', 'order': 3},
        {'name': 'Customer Service', 'name_ml': 'കസ്റ്റമർ സർവീസ്', 'slug': 'customer_service', 'order': 4},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 5},
    ],
    ShopCategory.BusinessType.OTHER_SERVICE: [
        {'name': 'Service Quality', 'name_ml': 'സേവന നിലവാരം', 'slug': 'service_quality', 'order': 1},
        {'name': 'Staff Behaviour', 'name_ml': 'ജീവനക്കാരുടെ പെരുമാറ്റം', 'slug': 'staff_behaviour', 'order': 2},
        {'name': 'Timeliness', 'name_ml': 'കൃത്യനിഷ്ഠ', 'slug': 'timeliness', 'order': 3},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 4},
        {'name': 'Customer Support', 'name_ml': 'കസ്റ്റമർ സപ്പോർട്ട്', 'slug': 'customer_support', 'order': 5},
    ],
    ShopCategory.BusinessType.MEDICAL: [
        {'name': 'Medicine Availability', 'name_ml': 'മരുന്നുകളുടെ ലഭ്യത', 'slug': 'medicine_availability', 'order': 1},
        {'name': 'Service Quality', 'name_ml': 'സേവന നിലവാരം', 'slug': 'service_quality', 'order': 2},
        {'name': 'Price / Value', 'name_ml': 'വില / മൂല്യം', 'slug': 'price_value', 'order': 3},
        {'name': 'Customer Support', 'name_ml': 'ഉപഭോക്തൃ സേവനം', 'slug': 'customer_support', 'order': 4},
    ],
}


class RatingCriterion(models.Model):
    """
    Dynamic rating criteria configured per business category or business type.
    Enables future categories to configure new criteria without changing code.
    """
    category = models.ForeignKey(
        ShopCategory,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='rating_criteria',
        verbose_name="ഷോപ്പ് വിഭാഗം (Specific Category)",
        help_text="Leave blank to apply to all categories of the selected business type"
    )
    business_type = models.CharField(
        max_length=30,
        choices=ShopCategory.BusinessType.choices,
        null=True,
        blank=True,
        verbose_name="സ്ഥാപന തരം (Business Type)",
        help_text="Default criteria applied across this business type"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="മാനദണ്ഡം (Criterion Name, e.g. Product Quality)"
    )
    name_ml = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="മലയാളം പേര് (Malayalam Name)"
    )
    slug = models.SlugField(
        max_length=100,
        verbose_name="സ്ലഗ് (Identifier Slug)"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="വിവരണം (Description)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="സജീവമാണോ (Is Active)"
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ക്രമം (Display Order)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "റേറ്റിംഗ് മാനദണ്ഡം (Rating Criterion)"
        verbose_name_plural = "റേറ്റിംഗ് മാനദണ്ഡങ്ങൾ (Rating Criteria)"
        ordering = ['order', 'name']

    def __str__(self):
        cat_or_bt = self.category.name if self.category else (self.get_business_type_display() or "All")
        return f"{self.name} ({cat_or_bt})"

class Shop(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shops',
        verbose_name="ഉടമസ്ഥൻ (Owner)"
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shops',
        verbose_name="പ്രദേശം (Area)"
    )
    category = models.ForeignKey(
        ShopCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='shops',
        verbose_name="വിഭാഗം (Category)"
    )
    name = models.CharField(max_length=200, verbose_name="സ്ഥാപനത്തിന്റെ പേര് (Shop Name)")
    description = models.TextField(blank=True, verbose_name="വിവരണം (Description)")
    contact_phone = models.CharField(max_length=17, verbose_name="ബന്ധപ്പെടേണ്ട നമ്പർ (Contact Phone)")
    whatsapp_number = models.CharField(max_length=17, blank=True, verbose_name="വാട്ട്സാപ്പ് നമ്പർ (WhatsApp)")
    address = models.TextField(verbose_name="വിലാസം (Address)")
    ward_number = models.PositiveSmallIntegerField(verbose_name="വാർഡ് നമ്പർ (Ward Number)")

    # OpenStreetMap GPS Coordinates (Free Tier Mapping)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_index=True)

    opening_time = models.TimeField(null=True, blank=True, verbose_name="തുറക്കുന്ന സമയം (Opening Time)")
    closing_time = models.TimeField(null=True, blank=True, verbose_name="അടയ്ക്കുന്ന സമയം (Closing Time)")
    is_open = models.BooleanField(default=True, verbose_name="ഇപ്പോൾ തുറന്നിരിക്കുന്നുണ്ടോ (Is Open Now)")
    is_temporarily_closed = models.BooleanField(default=False, verbose_name="താൽക്കാലികമായി അടച്ചിട്ടിരിക്കുന്നു (Temporarily Closed)")
    temporary_close_reason = models.CharField(max_length=255, blank=True, verbose_name="അടച്ചിടാനുള്ള കാരണം (Reason)")
    is_verified = models.BooleanField(default=False, verbose_name="പരിശോധിച്ച കട (Verified by Admin)")

    # Delivery & Offers
    delivery_available = models.BooleanField(default=False, verbose_name="ഹോം ഡെലിവറി ഉണ്ടോ")
    delivery_radius_km = models.DecimalField(max_digits=4, decimal_places=1, default=5.0, verbose_name="ഡെലിവറി പരിധി (km)")
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name="ഡെലിവറി ചാർജ്")
    todays_offer = models.TextField(blank=True, verbose_name="ഇന്നത്തെ ഓഫർ / സ്പെഷ്യൽ വിഭവം")

    banner_image = models.ImageField(upload_to='shops/banners/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ഷോപ്പ് (Shop)"
        verbose_name_plural = "ഷോപ്പുകൾ (Shops)"
        ordering = ['-is_open', 'name']

    def __str__(self):
        return f"{self.name} (വാർഡ് {self.ward_number})"

    @property
    def business_type(self):
        if self.category and hasattr(self.category, 'business_type') and self.category.business_type:
            return self.category.business_type
        # Heuristic fallback based on category name or interaction mode
        if self.category:
            cat_name = (self.category.name or '').lower()
            if any(k in cat_name for k in ['beauty', 'parlour', 'salon', 'പാർലർ', 'സലൂൺ', 'ബാർബർ']):
                return ShopCategory.BusinessType.BEAUTY_PARLOUR
            if any(k in cat_name for k in ['repair', 'വർക്ക്‌ഷോപ്പ്', 'റിപ്പയർ', 'സർവീസ്']):
                return ShopCategory.BusinessType.REPAIR
            if any(k in cat_name for k in ['pharmacy', 'medical', 'മരുന്ന്', 'ഫാർമസി', 'മെഡിക്കൽ']):
                return ShopCategory.BusinessType.MEDICAL
            if any(k in cat_name for k in ['restaurant', 'hotel', 'ഹോട്ടൽ', 'റസ്റ്റോറന്റ്', 'തട്ടുകട', 'ബേക്കറി', 'bakery']):
                return ShopCategory.BusinessType.RESTAURANT
            if self.category.interaction_mode == ShopCategory.InteractionMode.BOOKING:
                return ShopCategory.BusinessType.BEAUTY_PARLOUR
            if self.category.interaction_mode == ShopCategory.InteractionMode.REQUEST:
                return ShopCategory.BusinessType.REPAIR
        return ShopCategory.BusinessType.GENERAL

    @property
    def is_beauty_parlour(self):
        return self.business_type == ShopCategory.BusinessType.BEAUTY_PARLOUR

    @property
    def is_repair_shop(self):
        return self.business_type == ShopCategory.BusinessType.REPAIR

    @property
    def is_medical_shop(self):
        return self.business_type == ShopCategory.BusinessType.MEDICAL

    @property
    def is_restaurant(self):
        return self.business_type == ShopCategory.BusinessType.RESTAURANT

    @property
    def is_service_based(self):
        return self.business_type in [
            ShopCategory.BusinessType.BEAUTY_PARLOUR,
            ShopCategory.BusinessType.REPAIR,
            ShopCategory.BusinessType.OTHER_SERVICE
        ] or (self.category and self.category.interaction_mode in [
            ShopCategory.InteractionMode.BOOKING,
            ShopCategory.InteractionMode.REQUEST
        ])

    @property
    def is_product_based(self):
        return not self.is_service_based

    def get_progress(self):
        """Calculates onboarding and operational progress for this shop."""
        from apps.shops.services import ShopProgressCalculator
        return ShopProgressCalculator.calculate_progress(self)

    def get_business_status(self, now=None):
        """
        Calculates dynamic real-time operational status for this shop.
        Uses Asia/Kolkata timezone (IST) for local Kerala accuracy.
        """
        import zoneinfo
        from django.utils import timezone

        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        if now is None:
            current_dt = timezone.now().astimezone(kolkata_tz)
        else:
            if timezone.is_naive(now):
                current_dt = timezone.make_aware(now, kolkata_tz)
            else:
                current_dt = now.astimezone(kolkata_tz)

        current_weekday = current_dt.weekday()  # 0 = Monday, ..., 6 = Sunday
        current_time = current_dt.time()

        # 1. Emergency / Temporarily Closed override
        if self.is_temporarily_closed:
            return {
                'status_code': 'TEMPORARILY_CLOSED',
                'status_label': 'Temporarily Closed',
                'status_label_ml': 'താൽക്കാലികമായി അടച്ചിരിക്കുന്നു',
                'badge_color': 'rose',
                'is_open_now': False,
                'today_schedule': 'താൽക്കാലികമായി അടച്ചിരിക്കുന്നു (Temporarily Closed)',
                'is_temporarily_closed': True,
                'reason': self.temporary_close_reason or ''
            }

        # 2. Check 7-day schedule
        hours_qs = self.working_hours.all()
        day_hour = None
        has_weekly_schedule = False

        if hours_qs.exists():
            has_weekly_schedule = True
            day_hour = next((h for h in hours_qs if h.day == current_weekday), None)

        if day_hour:
            if day_hour.is_closed or (not day_hour.opening_time and not day_hour.closing_time):
                return {
                    'status_code': 'CLOSED_TODAY',
                    'status_label': 'CLOSED TODAY',
                    'status_label_ml': 'ഇന്ന് അവധിയാണ് (Closed Today)',
                    'badge_color': 'amber',
                    'is_open_now': False,
                    'today_schedule': 'അവധി (Closed)',
                    'is_temporarily_closed': False,
                    'reason': ''
                }
            ot = day_hour.opening_time
            ct = day_hour.closing_time
            schedule_str = f"{ot.strftime('%I:%M %p').lstrip('0')} - {ct.strftime('%I:%M %p').lstrip('0')}"

            if ot <= ct:
                is_within = (ot <= current_time < ct)
            else:
                # Overnight hours (e.g. 20:00 to 02:00)
                is_within = (current_time >= ot or current_time < ct)

            if is_within:
                return {
                    'status_code': 'OPEN',
                    'status_label': 'OPEN NOW',
                    'status_label_ml': 'ഇപ്പോൾ തുറന്നിരിക്കുന്നു (Open Now)',
                    'badge_color': 'emerald',
                    'is_open_now': True,
                    'today_schedule': schedule_str,
                    'is_temporarily_closed': False,
                    'reason': ''
                }
            else:
                return {
                    'status_code': 'CLOSED',
                    'status_label': 'CLOSED NOW',
                    'status_label_ml': 'ഇപ്പോൾ അടച്ചിരിക്കുന്നു (Closed Now)',
                    'badge_color': 'rose',
                    'is_open_now': False,
                    'today_schedule': schedule_str,
                    'is_temporarily_closed': False,
                    'reason': ''
                }

        # 3. Fallback to shop's single opening_time / closing_time
        if self.opening_time and self.closing_time:
            ot = self.opening_time
            ct = self.closing_time
            schedule_str = f"{ot.strftime('%I:%M %p').lstrip('0')} - {ct.strftime('%I:%M %p').lstrip('0')}"
            if ot <= ct:
                is_within = (ot <= current_time < ct)
            else:
                is_within = (current_time >= ot or current_time < ct)

            if is_within:
                return {
                    'status_code': 'OPEN',
                    'status_label': 'OPEN NOW',
                    'status_label_ml': 'ഇപ്പോൾ തുറന്നിരിക്കുന്നു (Open Now)',
                    'badge_color': 'emerald',
                    'is_open_now': True,
                    'today_schedule': schedule_str,
                    'is_temporarily_closed': False,
                    'reason': ''
                }
            else:
                return {
                    'status_code': 'CLOSED',
                    'status_label': 'CLOSED NOW',
                    'status_label_ml': 'ഇപ്പോൾ അടച്ചിരിക്കുന്നു (Closed Now)',
                    'badge_color': 'rose',
                    'is_open_now': False,
                    'today_schedule': schedule_str,
                    'is_temporarily_closed': False,
                    'reason': ''
                }

        # 4. Hours not set
        return {
            'status_code': 'HOURS_NOT_SET',
            'status_label': 'Hours not set',
            'status_label_ml': 'സമയം ചേർത്തിട്ടില്ല (Hours not set)',
            'badge_color': 'slate',
            'is_open_now': self.is_open,
            'today_schedule': 'പ്രവർത്തന സമയം ചേർത്തിട്ടില്ല',
            'is_temporarily_closed': False,
            'reason': ''
        }

    @property
    def business_status(self):
        return self.get_business_status()

    def get_weekly_schedule(self):
        """
        Returns an ordered list of 7 days with status for display.
        """
        import zoneinfo
        from django.utils import timezone
        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        current_weekday = timezone.now().astimezone(kolkata_tz).weekday()

        day_names = [
            (0, 'Monday', 'തിങ്കൾ (Monday)'),
            (1, 'Tuesday', 'ചൊവ്വ (Tuesday)'),
            (2, 'Wednesday', 'ബുധൻ (Wednesday)'),
            (3, 'Thursday', 'വ്യാഴം (Thursday)'),
            (4, 'Friday', 'വെള്ളി (Friday)'),
            (5, 'Saturday', 'ശനി (Saturday)'),
            (6, 'Sunday', 'ഞായർ (Sunday)'),
        ]

        hours_map = {h.day: h for h in self.working_hours.all()}
        schedule = []
        for idx, en_name, ml_name in day_names:
            h = hours_map.get(idx)
            is_today = (idx == current_weekday)
            if h:
                if h.is_closed or (not h.opening_time and not h.closing_time):
                    display = "അവധി (Closed)"
                    is_closed = True
                else:
                    display = f"{h.opening_time.strftime('%I:%M %p').lstrip('0')} - {h.closing_time.strftime('%I:%M %p').lstrip('0')}"
                    is_closed = False
            elif self.opening_time and self.closing_time:
                display = f"{self.opening_time.strftime('%I:%M %p').lstrip('0')} - {self.closing_time.strftime('%I:%M %p').lstrip('0')}"
                is_closed = False
            else:
                display = "ചേർത്തിട്ടില്ല (Not set)"
                is_closed = False

            schedule.append({
                'day': idx,
                'name_en': en_name,
                'name_ml': ml_name,
                'is_today': is_today,
                'is_closed': is_closed,
                'opening_time': h.opening_time if h else self.opening_time,
                'closing_time': h.closing_time if h else self.closing_time,
                'display': display,
                'schedule_display': display,
            })
        return schedule

    def get_rating_criteria(self):
        """
        Returns active rating criteria configured for this shop's category/business type.
        Supports dynamic addition/editing of criteria by Admin without code changes.
        Falls back to category defaults if database has not been seeded yet.
        """
        criteria = []
        if self.category:
            cat_criteria = self.category.rating_criteria.filter(is_active=True).order_by('order', 'id')
            if cat_criteria.exists():
                return [
                    {
                        'id': c.id,
                        'name': c.name,
                        'name_ml': c.name_ml or c.name,
                        'slug': c.slug,
                        'description': c.description,
                        'order': c.order,
                    }
                    for c in cat_criteria
                ]

        bt = self.business_type
        bt_criteria = RatingCriterion.objects.filter(
            category__isnull=True,
            business_type=bt,
            is_active=True
        ).order_by('order', 'id')
        if bt_criteria.exists():
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'name_ml': c.name_ml or c.name,
                    'slug': c.slug,
                    'description': c.description,
                    'order': c.order,
                }
                for c in bt_criteria
            ]

        # Built-in fallback
        defaults = DEFAULT_RATING_CRITERIA.get(bt, DEFAULT_RATING_CRITERIA.get(ShopCategory.BusinessType.GENERAL, []))
        return [
            {
                'id': None,
                'name': d['name'],
                'name_ml': d.get('name_ml', d['name']),
                'slug': d['slug'],
                'description': d.get('description', ''),
                'order': d.get('order', idx),
            }
            for idx, d in enumerate(defaults, 1)
        ]

    def get_rating_summary(self):
        """
        Comprehensive Category-Based Rating Summary:
        - overall_average_rating: STRICTLY based on overall star ratings of all valid reviews.
        - total_reviews: total count of verified buyer reviews.
        - verified_reviews_count: verified reviews.
        - star_distribution: 5★ to 1★ counts and percentages.
        - criteria_averages: category scores calculated separately (never averaged together for overall).
        - recent_reviews: latest reviews with detailed criteria scores and feedback.
        """
        from django.db.models import Avg

        reviews_qs = self.reviews.select_related('user', 'order', 'booking').all()
        total_reviews = reviews_qs.count()
        verified_count = reviews_qs.filter(is_verified_buyer=True).count()

        # Rule: Overall rating is strictly based on overall star ratings of reviews
        if total_reviews > 0:
            avg_rating = reviews_qs.aggregate(Avg('rating'))['rating__avg']
            overall_average_rating = round(float(avg_rating), 1) if avg_rating is not None else 0.0
        else:
            overall_average_rating = 0.0

        # Star distribution (5 down to 1)
        star_distribution = {}
        for star in [5, 4, 3, 2, 1]:
            count = reviews_qs.filter(rating=star).count()
            pct = round((count / total_reviews) * 100, 1) if total_reviews > 0 else 0.0
            star_distribution[star] = {
                'star': star,
                'count': count,
                'percentage': pct,
            }

        # Category scores calculated separately
        criteria = self.get_rating_criteria()
        criteria_averages = []
        for crit in criteria:
            slug = crit['slug']
            name = crit['name']
            name_ml = crit.get('name_ml', name)

            crit_qs = ReviewCriterionRating.objects.filter(
                review__shop=self,
                criterion_slug=slug
            )
            c_count = crit_qs.count()
            c_avg = crit_qs.aggregate(Avg('rating'))['rating__avg'] if c_count > 0 else None
            criteria_averages.append({
                'slug': slug,
                'name': name,
                'name_ml': name_ml,
                'average': round(float(c_avg), 1) if c_avg is not None else 0.0,
                'count': c_count,
            })

        # Recent reviews with criteria breakdown
        recent_reviews = []
        for rev in reviews_qs.order_by('-created_at')[:8]:
            c_ratings = []
            for cr in rev.criterion_ratings.all():
                c_ratings.append({
                    'criterion_name': cr.criterion_name,
                    'criterion_name_ml': cr.criterion_name_ml,
                    'criterion_slug': cr.criterion_slug,
                    'rating': cr.rating,
                    'feedback': cr.feedback,
                })
            recent_reviews.append({
                'id': rev.id,
                'user_name': rev.user.full_name or rev.user.phone_number,
                'user_phone': rev.user.phone_number,
                'rating': rev.rating,
                'comment': rev.comment,
                'is_verified_buyer': rev.is_verified_buyer,
                'order_id': rev.order_id,
                'booking_id': rev.booking_id,
                'created_at': rev.created_at,
                'criterion_ratings': c_ratings,
            })

        return {
            'overall_average_rating': overall_average_rating,
            'total_reviews': total_reviews,
            'verified_reviews_count': verified_count,
            'star_distribution': star_distribution,
            'criteria_averages': criteria_averages,
            'recent_reviews': recent_reviews,
        }


class ShopWorkingHour(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'തിങ്കൾ (Monday)'
        TUESDAY = 1, 'ചൊവ്വ (Tuesday)'
        WEDNESDAY = 2, 'ബുധൻ (Wednesday)'
        THURSDAY = 3, 'വ്യാഴം (Thursday)'
        FRIDAY = 4, 'വെള്ളി (Friday)'
        SATURDAY = 5, 'ശനി (Saturday)'
        SUNDAY = 6, 'ഞായർ (Sunday)'

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='working_hours',
        verbose_name="സ്ഥാപനം (Shop)"
    )
    day = models.PositiveSmallIntegerField(
        choices=DayOfWeek.choices,
        verbose_name="ദിവസം (Day)"
    )
    opening_time = models.TimeField(null=True, blank=True, verbose_name="തുറക്കുന്ന സമയം (Opening Time)")
    closing_time = models.TimeField(null=True, blank=True, verbose_name="അടയ്ക്കുന്ന സമയം (Closing Time)")
    is_closed = models.BooleanField(default=False, verbose_name="അവധിദിനം / അടച്ചിരിക്കുന്നു (Closed / Holiday)")

    class Meta:
        verbose_name = "പ്രവർത്തന സമയം (Working Hour)"
        verbose_name_plural = "പ്രവർത്തന സമയങ്ങൾ (Working Hours)"
        unique_together = ('shop', 'day')
        ordering = ['day']

    def __str__(self):
        day_name = self.get_day_display()
        if self.is_closed:
            return f"{self.shop.name} - {day_name}: അടച്ചിരിക്കുന്നു (Closed)"
        return f"{self.shop.name} - {day_name}: {self.opening_time} - {self.closing_time}"

class Product(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="സ്ഥാപനം (Shop)"
    )
    name = models.CharField(max_length=200, verbose_name="ഉൽപ്പന്നം / വിഭവം / സേവനം")
    description = models.TextField(blank=True, verbose_name="വിവരണം (Description)")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="വില (Price)")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="ഓഫർ വില (Offer Price)")
    unit = models.CharField(max_length=50, default='1 unit', help_text="e.g., 1 kg, 500g, 1 plate, 1 pc, 1 hr", verbose_name="അളവ് / യൂണിറ്റ്")
    service_duration_minutes = models.PositiveIntegerField(null=True, blank=True, verbose_name="സമയദൈർഘ്യം (മിനിറ്റ്)")
    is_available = models.BooleanField(default=True, verbose_name="ലഭ്യമാണോ (In Stock)")
    requires_prescription = models.BooleanField(
        default=False,
        verbose_name="ഡോക്ടറുടെ കുറിപ്പടി ആവശ്യമുള്ളത് (Requires Prescription)"
    )
    expiry_info = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="കാലാവധി വിവരങ്ങൾ (Expiry Info)"
    )
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ഉൽപ്പന്നം / മെനു / സേവനം"
        verbose_name_plural = "ഉൽപ്പന്നങ്ങൾ & സേവനങ്ങൾ"
        ordering = ['-is_available', 'name']

    def __str__(self):
        return f"{self.name} - ₹{self.price} ({self.shop.name})"

    @property
    def is_service(self):
        return bool(self.service_duration_minutes) or (self.shop and self.shop.is_service_based)

    @property
    def duration_display(self):
        if self.service_duration_minutes:
            if self.service_duration_minutes >= 60:
                hours = self.service_duration_minutes // 60
                mins = self.service_duration_minutes % 60
                if mins:
                    return f"{hours} മണിക്കൂർ {mins} മിനിറ്റ് ({self.service_duration_minutes} മിനിറ്റ്)"
                return f"{hours} മണിക്കൂർ ({self.service_duration_minutes} മിനിറ്റ്)"
            return f"{self.service_duration_minutes} മിനിറ്റ്"
        return self.unit or ""

class Review(models.Model):
    """
    Shop Reviews & Ratings.
    Only buyers who completed an order or booking can leave verified ratings!
    """
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="ഷോപ്പ്"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shop_reviews',
        verbose_name="ഉപയോക്താവ്"
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name="ഓർഡർ (Order)"
    )
    booking = models.ForeignKey(
        'orders.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        verbose_name="ബുക്കിംഗ് (Booking)"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')],
        verbose_name="റേറ്റിംഗ്"
    )
    comment = models.TextField(blank=True, verbose_name="അഭിപ്രായം (Review)")
    is_verified_buyer = models.BooleanField(default=False, verbose_name="വാങ്ങിയ ആളുടെ റിവ്യൂ (Verified Buyer)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "റിവ്യൂ & റേറ്റിംഗ് (Review)"
        verbose_name_plural = "റിവ്യൂകൾ & റേറ്റിംഗുകൾ (Reviews)"
        ordering = ['-created_at']
        unique_together = ('shop', 'user')

    def __str__(self):
        return f"{self.shop.name} - {self.rating}★ by {self.user.full_name}"


class ReviewCriterionRating(models.Model):
    """
    Individual rating score (1-5 stars) and optional written feedback for a category criterion.
    Retains snapshot of criterion name and slug to preserve historical reviews
    even if the criterion is later modified or disabled.
    """
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='criterion_ratings',
        verbose_name="റിവ്യൂ (Review)"
    )
    criterion = models.ForeignKey(
        RatingCriterion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='criterion_scores',
        verbose_name="മാനദണ്ഡം (Criterion)"
    )
    criterion_name = models.CharField(
        max_length=100,
        verbose_name="മാനദണ്ഡം (Criterion Name Snapshot)"
    )
    criterion_name_ml = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="മലയാളം പേര് (Malayalam Snapshot)"
    )
    criterion_slug = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="സ്ലഗ് (Snapshot Slug)"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')],
        verbose_name="റേറ്റിംഗ് (1-5 Stars)"
    )
    feedback = models.TextField(
        blank=True,
        verbose_name="പ്രത്യേക അഭിപ്രായം (Optional Feedback)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "മാനദണ്ഡ റേറ്റിംഗ് (Review Criterion Rating)"
        verbose_name_plural = "മാനദണ്ഡ റേറ്റിംഗുകൾ (Review Criterion Ratings)"
        unique_together = ('review', 'criterion_slug')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.review.shop.name} - {self.criterion_name}: {self.rating}★"

