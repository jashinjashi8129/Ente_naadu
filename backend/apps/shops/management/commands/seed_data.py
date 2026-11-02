from django.core.management.base import BaseCommand
from decimal import Decimal
from apps.shops.models import ShopCategory, Shop, Product
from apps.accounts.models import Area, User
from apps.directory.models import DirectoryEntry, BloodDonor, ClassifiedAd
from apps.events.models import EventNotice
from apps.orders.models import Order, OrderItem
from apps.complaints.models import Complaint

CATEGORIES = [
    # 1. ORDER Mode (ഹോട്ടൽ ഭക്ഷണം, പലചരക്ക്, ബേക്കറി)
    {
        "name": "പലചരക്ക് & സൂപ്പർമാർക്കറ്റ് (Groceries)",
        "description": "അരി, ധാന്യങ്ങൾ, എണ്ണ, നിത്യോപയോഗ സാധനങ്ങൾ",
        "icon_name": "local_grocery_store",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.GENERAL
    },
    {
        "name": "ഹോട്ടൽ & റെസ്റ്റോറന്റുകൾ (Hotels & Food)",
        "description": "പ്രഭാതഭക്ഷണം, ഊണ്, രാത്രി ഭക്ഷണം, ലഘുഭക്ഷണങ്ങൾ",
        "icon_name": "restaurant",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.RESTAURANT
    },
    {
        "name": "ബേക്കറി & കൂൾബാർ (Bakery & Cool Bar)",
        "description": "ചായ, ലഘുഭക്ഷണങ്ങൾ, ജ്യൂസ്, കേക്കുകൾ, ബ്രെഡ്",
        "icon_name": "cake",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.RESTAURANT
    },
    {
        "name": "പച്ചക്കറി & പഴങ്ങൾ (Vegetables & Fruits)",
        "description": "ശുദ്ധമായ പച്ചക്കറികൾ, പഴവർഗ്ഗങ്ങൾ",
        "icon_name": "eco",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.GENERAL
    },
    {
        "name": "മീൻ & ഇറച്ചി മാർക്കറ്റ് (Fish & Meat)",
        "description": "ശുദ്ധമായ മീൻ, ചിക്കൻ, മട്ടൻ, ബീഫ്",
        "icon_name": "set_meal",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.GENERAL
    },

    # 2. BOOKING Mode (ബാർബർ, ബ്യൂട്ടി പാർലർ, അക്ഷയ)
    {
        "name": "ബ്യൂട്ടി പാർലർ & സലൂൺ (Beauty Parlour & Salon)",
        "description": "ഫേഷ്യൽ, ഹെയർ കട്ടിംഗ്, ബ്രൈഡൽ മേക്കപ്പ്, സ്പാ സമയം ബുക്കിംഗ്",
        "icon_name": "face",
        "interaction_mode": ShopCategory.InteractionMode.BOOKING,
        "business_type": ShopCategory.BusinessType.BEAUTY_PARLOUR
    },
    {
        "name": "ബാർബർ ഷോപ്പ് & മെൻസ് ഗ്രൂമിംഗ് (Barber & Men's Grooming)",
        "description": "ഹെയർ കട്ടിംഗ്, ഷേവിംഗ്, മസാജ് സമയം ബുക്കിംഗ്",
        "icon_name": "content_cut",
        "interaction_mode": ShopCategory.InteractionMode.BOOKING,
        "business_type": ShopCategory.BusinessType.BEAUTY_PARLOUR
    },
    {
        "name": "അക്ഷയ & ജനസേവന കേന്ദ്രം (Akshaya Center)",
        "description": "സർക്കാർ സേവനങ്ങൾ, അപേക്ഷകൾ, ടോക്കൺ ബുക്കിംഗ്",
        "icon_name": "how_to_reg",
        "interaction_mode": ShopCategory.InteractionMode.BOOKING,
        "business_type": ShopCategory.BusinessType.OTHER_SERVICE
    },

    # 3. REQUEST / SERVICE Mode (റിപ്പയറിംഗ്, മെഡിക്കൽ, ടെയ്‌ലറിംഗ്)
    {
        "name": "മെഡിക്കൽ സ്റ്റോർ (Pharmacy & Medical)",
        "description": "കുറിപ്പടി / മരുന്നിന്റെ ഫോട്ടോ അയച്ച് ലഭ്യത അന്വേഷിക്കുക",
        "icon_name": "local_pharmacy",
        "interaction_mode": ShopCategory.InteractionMode.REQUEST,
        "business_type": ShopCategory.BusinessType.MEDICAL
    },
    {
        "name": "റിപ്പയർ & സർവീസ് സെന്റർ (Repair & Services)",
        "description": "ഇലക്ട്രിക്കൽ, പ്ലംബിംഗ്, മൊബൈൽ & അപ്ലയൻസ് റിപ്പയറിംഗ്",
        "icon_name": "build",
        "interaction_mode": ShopCategory.InteractionMode.REQUEST,
        "business_type": ShopCategory.BusinessType.REPAIR
    },
    {
        "name": "ടെയ്‌ലറിംഗ് & സ്റ്റിച്ചിംഗ് (Tailoring & Design)",
        "description": "അളവുകളും ഡിസൈൻ ഫോട്ടോയും നൽകി തയ്യൽ അന്വേഷണം",
        "icon_name": "checkroom",
        "interaction_mode": ShopCategory.InteractionMode.REQUEST,
        "business_type": ShopCategory.BusinessType.OTHER_SERVICE
    },
    {
        "name": "സ്റ്റേഷനറി & പ്രിന്റിംഗ് (Stationery & Xerox)",
        "description": "പുസ്തകങ്ങൾ, പ്രിന്റിംഗ് ഓർഡറുകൾ",
        "icon_name": "menu_book",
        "interaction_mode": ShopCategory.InteractionMode.ORDER,
        "business_type": ShopCategory.BusinessType.GENERAL
    }
]

class Command(BaseCommand):
    help = "Seeds initial area and shop categories with interaction modes (Order, Booking, Request)"

    def handle(self, *args, **options):
        # 1. Seed Default Area
        area, area_created = Area.objects.get_or_create(
            name="എന്റെ നാട് (പഞ്ചായത്ത്)",
            defaults={
                "district": "തിരുവനന്തപുരം",
                "state": "കേരളം",
                "pincode": "695001",
                "is_active": True
            }
        )
        if area_created:
            self.stdout.write(self.style.SUCCESS(f"Created default Area: {area.name}"))

        # 2. Seed Categories
        count = 0
        for item in CATEGORIES:
            category, created = ShopCategory.objects.get_or_create(
                name=item["name"],
                defaults={
                    "description": item["description"],
                    "icon_name": item["icon_name"],
                    "interaction_mode": item["interaction_mode"],
                    "business_type": item.get("business_type", ShopCategory.BusinessType.GENERAL),
                }
            )
            update_fields = []
            if not created:
                if category.interaction_mode != item["interaction_mode"]:
                    category.interaction_mode = item["interaction_mode"]
                    update_fields.append('interaction_mode')
                if hasattr(category, 'business_type') and category.business_type != item.get("business_type"):
                    category.business_type = item.get("business_type", ShopCategory.BusinessType.GENERAL)
                    update_fields.append('business_type')
                if update_fields:
                    category.save(update_fields=update_fields)

            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f"Created category: {category.name} ({category.interaction_mode})"))
            else:
                self.stdout.write(f"Updated/Confirmed category: {category.name}")

        self.stdout.write(self.style.SUCCESS(f"Categories verified. Total {count} new categories added."))

        # 3. Seed Sample Verified Shop Owner
        owner, owner_created = User.objects.get_or_create(
            phone_number="9876543210",
            defaults={
                "full_name": "സുരേഷ് കുമാർ (വ്യാപാരി)",
                "role": User.Role.SHOP_OWNER,
                "area": area,
                "ward_number": 3,
                "address": "മെയിൻ റോഡ്, ജംഗ്ഷൻ"
            }
        )
        if owner_created:
            owner.set_password("pass1234")
            owner.save()
            self.stdout.write(self.style.SUCCESS(f"Created sample Shop Owner: {owner.full_name} (9876543210 / pass1234)"))

        # 4. Seed Sample Verified Shops
        cat_grocery = ShopCategory.objects.filter(name__icontains="പലചരക്ക്").first()
        cat_hotel = ShopCategory.objects.filter(name__icontains="ഹോട്ടൽ").first()
        cat_bakery = ShopCategory.objects.filter(name__icontains="ബേക്കറി").first()
        cat_veg = ShopCategory.objects.filter(name__icontains="പച്ചക്കറി").first()
        cat_salon = ShopCategory.objects.filter(name__icontains="ബാർബർ").first()
        cat_medical = ShopCategory.objects.filter(name__icontains="മെഡിക്കൽ").first()

        sample_shops = [
            {
                "name": "നാട്ടുപീടിക പലചരക്ക് സ്റ്റോർ",
                "category": cat_grocery,
                "owner_phone": "9876543210",
                "owner_name": "സുരേഷ് കുമാർ (വ്യാപാരി)",
                "description": "ശുദ്ധമായ വെളിച്ചെണ്ണ, നാടൻ അരി, നിത്യോപയോഗ സാധനങ്ങൾ എല്ലാം ഇവിടെ ലഭ്യമാണ്.",
                "contact_phone": "9876543210",
                "whatsapp_number": "9876543210",
                "address": "സെൻട്രൽ ജംഗ്ഷൻ, പഞ്ചായത്ത് ഓഫീസ് റോഡ്",
                "ward_number": 3,
                "is_open": True,
                "is_verified": True,
                "delivery_available": True,
                "todays_offer": "ജയ അരി 10 കിലോ ചാക്കിന് ₹50 കിഴിവ്!",
                "products": [
                    {"name": "നാടൻ ജയ അരി (10 kg)", "price": Decimal("450.00"), "unit": "10 kg bag"},
                    {"name": "ശുദ്ധമായ വെളിച്ചെണ്ണ (1 Ltr)", "price": Decimal("230.00"), "unit": "1 Litre"},
                    {"name": "സ്പെഷ്യൽ തേയിലപ്പൊടി (500g)", "price": Decimal("140.00"), "unit": "500g pack"},
                    {"name": "ചെറുപയർ പരിപ്പ് (1 kg)", "price": Decimal("110.00"), "unit": "1 kg pack"},
                    {"name": "നാടൻ കാപ്പിപ്പൊടി (250g)", "price": Decimal("90.00"), "unit": "250g pack"},
                ]
            },
            {
                "name": "മലബാർ കഫേ & റെസ്റ്റോറന്റ്",
                "category": cat_hotel,
                "owner_phone": "9876543211",
                "owner_name": "ഫൈസൽ റഹ്മാൻ (ഹോട്ടൽ ഉടമ)",
                "description": "ചൂടൻ പൊറോട്ട, ചിക്കൻ ബിരിയാണി, ദം ടീ, സ്വാദിഷ്ടമായ നാടൻ വിഭവങ്ങൾ.",
                "contact_phone": "9876543211",
                "whatsapp_number": "9876543211",
                "address": "ബസ് സ്റ്റാൻഡ് റോഡ്, വാർഡ് 4",
                "ward_number": 4,
                "is_open": True,
                "is_verified": True,
                "delivery_available": True,
                "todays_offer": "സ്പെഷ്യൽ ദം ബിരിയാണിക്കൊപ്പം ഫ്രീ കൂൾ ഡ്രിങ്ക്!",
                "products": [
                    {"name": "തലശ്ശേരി ചിക്കൻ ബിരിയാണി", "price": Decimal("160.00"), "unit": "1 Plate"},
                    {"name": "കേരള പൊറോട്ട", "price": Decimal("12.00"), "unit": "1 Piece"},
                    {"name": "ചിക്കൻ റോസ്റ്റ്", "price": Decimal("140.00"), "unit": "1 Plate"},
                    {"name": "സ്പെഷ്യൽ മസാല ചായ", "price": Decimal("15.00"), "unit": "1 Cup"},
                    {"name": "നെയ്ച്ചോറും ബീഫ് കറിയും", "price": Decimal("170.00"), "unit": "1 Plate"},
                ]
            },
            {
                "name": "ഗ്രീൻ വാലി ബേക്കറി & കൂൾബാർ",
                "category": cat_bakery,
                "owner_phone": "9876543214",
                "owner_name": "തോമസ് വർഗ്ഗീസ് (ബേക്കറി)",
                "description": "ഫ്രഷ് കേക്കുകൾ, ബ്രെഡ്, ചൂടൻ പഫ്സ്, ഐസ്ക്രീം, ഫ്രഷ് ജ്യൂസുകൾ.",
                "contact_phone": "9876543214",
                "whatsapp_number": "9876543214",
                "address": "കോളേജ് ജംഗ്ഷൻ, വാർഡ് 2",
                "ward_number": 2,
                "is_open": True,
                "is_verified": True,
                "delivery_available": True,
                "todays_offer": "ബർത്ത്ഡേ കേക്കുകൾക്ക് 15% ഓഫർ!",
                "products": [
                    {"name": "പാല് ബ്രെഡ് (400g)", "price": Decimal("45.00"), "unit": "1 Loaf"},
                    {"name": "ചിക്കൻ പഫ്സ്", "price": Decimal("25.00"), "unit": "1 Piece"},
                    {"name": "എഗ്ഗ് പഫ്സ്", "price": Decimal("20.00"), "unit": "1 Piece"},
                    {"name": "ഷാർജ ഷേക്ക് (Special)", "price": Decimal("60.00"), "unit": "1 Glass"},
                    {"name": "ബ്ലാക്ക് ഫോറസ്റ്റ് കേക്ക് (500g)", "price": Decimal("380.00"), "unit": "500g"},
                ]
            },
            {
                "name": "ഫ്രഷ് നാടൻ പച്ചക്കറി & പഴക്കട",
                "category": cat_veg,
                "owner_phone": "9876543215",
                "owner_name": "രാധാകൃഷ്ണൻ നായർ (പച്ചക്കറിക്കട)",
                "description": "കർഷകരിൽ നിന്ന് നേരിട്ട് ശേഖരിക്കുന്ന വിഷരഹിത പച്ചക്കറികളും നാടൻ പഴങ്ങളും.",
                "contact_phone": "9876543215",
                "whatsapp_number": "9876543215",
                "address": "മാർക്കറ്റ് റോഡ്, വാർഡ് 3",
                "ward_number": 3,
                "is_open": True,
                "is_verified": True,
                "delivery_available": True,
                "todays_offer": "ഞാലിപ്പൂവൻ പഴത്തിന് കിലോയ്ക്ക് ₹10 കിഴിവ്!",
                "products": [
                    {"name": "നാടൻ തക്കാളി (1 kg)", "price": Decimal("30.00"), "unit": "1 kg"},
                    {"name": "സവാള (1 kg)", "price": Decimal("40.00"), "unit": "1 kg"},
                    {"name": "ഉരുളക്കിഴങ്ങ് (1 kg)", "price": Decimal("35.00"), "unit": "1 kg"},
                    {"name": "പച്ചമുളക് (250g)", "price": Decimal("20.00"), "unit": "250g pack"},
                    {"name": "ഞാലിപ്പൂവൻ പഴം (1 kg)", "price": Decimal("65.00"), "unit": "1 kg"},
                ]
            },
            {
                "name": "റോയൽ ഹെയർ കട്ടിംഗ് & സ്പാ",
                "category": cat_salon,
                "owner_phone": "9876543212",
                "owner_name": "മനോജ് കുമാർ (സലൂൺ ഉടമ)",
                "description": "മോഡേൺ ഹെയർ ഡ്രസ്സിംഗ്, ഷേവിംഗ്, ഫേഷ്യൽ. ആപ്പ് വഴി മുൻകൂട്ടി സമയം ബുക്ക് ചെയ്യാം.",
                "contact_phone": "9876543212",
                "whatsapp_number": "9876543212",
                "address": "മാർക്കറ്റ് റോഡ്, വാർഡ് 2",
                "ward_number": 2,
                "is_open": True,
                "is_verified": True,
                "delivery_available": False,
                "todays_offer": "ഫേഷ്യൽ ബുക്കിംഗിന് 20% സ്പെഷ്യൽ ഡിസ്കൗണ്ട്!",
                "products": [
                    {"name": "ഹെയർ കട്ടിംഗ് & സ്റ്റൈലിംഗ്", "price": Decimal("120.00"), "unit": "20 mins", "service_duration_minutes": 20, "description": "സ്റ്റൈലിഷ് ഹെയർ കട്ട് & വാഷ്"},
                    {"name": "ഷേവിംഗ് & ബിയേർഡ് ട്രിമ്മിംഗ്", "price": Decimal("80.00"), "unit": "15 mins", "service_duration_minutes": 15, "description": "ക്ലീൻ ഷേവിംഗ് & ബിയേർഡ് സെറ്റിംഗ്"},
                    {"name": "ഹെർബൽ ഫേഷ്യൽ", "price": Decimal("350.00"), "unit": "45 mins", "service_duration_minutes": 45, "description": "പ്രകൃതിദത്ത ഔഷധക്കൂട്ടുകൾ ചേർത്ത ഫേഷ്യൽ"},
                ]
            },
            {
                "name": "ലക്ഷ്മി ബ്യൂട്ടി പാർലർ & സ്പാ",
                "category": cat_salon,
                "owner_phone": "9876543216",
                "owner_name": "ലക്ഷ്മി പ്രിയ (ബ്യൂട്ടി തെറാപ്പിസ്റ്റ്)",
                "description": "ബ്രൈഡൽ മേക്കപ്പ്, ഫേഷ്യൽ, ഹെയർ സ്പാ, ത്വക്ക് സംരക്ഷണം. മുൻകൂട്ടി സമയം ബുക്ക് ചെയ്യാം.",
                "contact_phone": "9876543216",
                "whatsapp_number": "9876543216",
                "address": "ടെമ്പിൾ റോഡ്, വാർഡ് 1",
                "ward_number": 1,
                "is_open": True,
                "is_verified": True,
                "delivery_available": False,
                "todays_offer": "ബ്രൈഡൽ പാക്കേജിന് 15% പ്രത്യേക ഓഫർ!",
                "products": [
                    {"name": "ബ്രൈഡൽ മേക്കപ്പ് & ഹെയർ സ്റ്റൈലിംഗ്", "price": Decimal("2500.00"), "unit": "90 മിനിറ്റ്", "service_duration_minutes": 90, "description": "പ്രൊഫഷണൽ ബ്രൈഡൽ മേക്കപ്പും സാരി ഡ്രേപ്പിംഗും"},
                    {"name": "ഗോൾഡ് ഗ്ലോ ഫേഷ്യൽ", "price": Decimal("650.00"), "unit": "45 മിനിറ്റ്", "service_duration_minutes": 45, "description": "മുഖകാന്തി വർദ്ധിപ്പിക്കുന്ന സ്പെഷ്യൽ ഫേഷ്യൽ"},
                    {"name": "ഹെയർ സ്പാ & ഡീപ് കണ്ടീഷനിംഗ്", "price": Decimal("800.00"), "unit": "60 മിനിറ്റ്", "service_duration_minutes": 60, "description": "മുടി കൊഴിച്ചിൽ തടയാനുള്ള ആഴത്തിലുള്ള ട്രീറ്റ്മെന്റ്"},
                    {"name": "ഐബ്രോ ത്രെഡിംഗ് & പെഡിക്യൂർ", "price": Decimal("250.00"), "unit": "30 മിനിറ്റ്", "service_duration_minutes": 30, "description": "ക്ലീൻ അപ്പ്, ത്രെഡിംഗ്, പെഡിക്യൂർ"},
                ]
            },
            {
                "name": "ജീവൻ ഫാർമസി & മെഡിക്കൽസ്",
                "category": cat_medical,
                "owner_phone": "9876543213",
                "owner_name": "ഡോ. പ്രദീപ് കുമാർ (ഫാർമസിസ്റ്റ്)",
                "description": "എല്ലാ അവശ്യ ജീവൻരക്ഷാ മരുന്നുകളും ഇവിടെ ലഭ്യം. കുറിപ്പടി ഫോട്ടോ അയക്കാം.",
                "contact_phone": "9876543213",
                "whatsapp_number": "9876543213",
                "address": "ഗവ. ഹോസ്പിറ്റൽ ജംഗ്ഷൻ, വാർഡ് 1",
                "ward_number": 1,
                "is_open": True,
                "is_verified": True,
                "delivery_available": True,
                "todays_offer": "ബിപി, ഷുഗർ പരിശോധന തികച്ചും സൗജന്യം!",
                "products": [
                    {"name": "പാരസെറ്റമോൾ 650mg (10 ഗുളികകൾ)", "price": Decimal("30.00"), "discount_price": Decimal("25.00"), "unit": "1 Strip", "requires_prescription": False, "expiry_info": "12/2027"},
                    {"name": "അമോക്സിസിലിൻ 500mg ആന്റിബയോട്ടിക്", "price": Decimal("110.00"), "discount_price": Decimal("95.00"), "unit": "1 Strip", "requires_prescription": True, "expiry_info": "08/2027"},
                    {"name": "ഫസ്റ്റ് എയ്ഡ് ബാൻഡേജ് കിറ്റ്", "price": Decimal("120.00"), "unit": "1 Kit", "requires_prescription": False},
                    {"name": "ഡിജിറ്റൽ തെർമോമീറ്റർ", "price": Decimal("180.00"), "discount_price": Decimal("160.00"), "unit": "1 Piece", "requires_prescription": False},
                ]
            }
        ]

        for s_data in sample_shops:
            products_data = s_data.pop("products")
            owner_phone = s_data.pop("owner_phone", "9876543210")
            owner_name = s_data.pop("owner_name", "വ്യാപാരി")

            shop_owner, _ = User.objects.get_or_create(
                phone_number=owner_phone,
                defaults={
                    "full_name": owner_name,
                    "role": User.Role.SHOP_OWNER,
                    "area": area,
                    "ward_number": s_data["ward_number"],
                    "address": s_data["address"]
                }
            )
            if _:
                shop_owner.set_password("pass1234")
                shop_owner.save()

            shop, s_created = Shop.objects.get_or_create(
                name=s_data["name"],
                defaults={
                    "owner": shop_owner,
                    "area": area,
                    "category": s_data["category"],
                    "description": s_data["description"],
                    "contact_phone": s_data["contact_phone"],
                    "whatsapp_number": s_data["whatsapp_number"],
                    "address": s_data["address"],
                    "ward_number": s_data["ward_number"],
                    "is_open": s_data["is_open"],
                    "is_verified": s_data["is_verified"],
                    "delivery_available": s_data["delivery_available"],
                    "todays_offer": s_data["todays_offer"],
                }
            )
            if not s_created and shop.owner != shop_owner:
                shop.owner = shop_owner
                shop.save(update_fields=['owner'])

            if s_created:
                self.stdout.write(self.style.SUCCESS(f"Created verified sample shop: {shop.name} (Owner: {shop_owner.full_name})"))
            else:
                self.stdout.write(f"Confirmed shop: {shop.name} (Owner: {shop.owner.full_name})")

            for p in products_data:
                product, p_created = Product.objects.get_or_create(
                    shop=shop,
                    name=p["name"],
                    defaults={
                        "price": p["price"],
                        "discount_price": p.get("discount_price"),
                        "unit": p.get("unit", "1 unit"),
                        "service_duration_minutes": p.get("service_duration_minutes"),
                        "description": p.get("description", ""),
                        "requires_prescription": p.get("requires_prescription", False),
                        "expiry_info": p.get("expiry_info", ""),
                        "is_available": True
                    }
                )
                if not p_created:
                    update_p = []
                    if p.get("service_duration_minutes") and not product.service_duration_minutes:
                        product.service_duration_minutes = p.get("service_duration_minutes")
                        update_p.append("service_duration_minutes")
                    if p.get("description") and not product.description:
                        product.description = p.get("description")
                        update_p.append("description")
                    if update_p:
                        product.save(update_fields=update_p)
                if p_created:
                    self.stdout.write(self.style.SUCCESS(f"  + Added catalog item: {product.name} (₹{product.price})"))

        # 5. Seed Directory & Emergency Services
        sample_directory = [
            {"name": "24/7 ജീവൻരക്ഷാ ആംബുലൻസ്", "category": DirectoryEntry.Category.AMBULANCE, "phone_number": "9447108108", "address_or_stand": "പഞ്ചായത്ത് ജംഗ്ഷൻ", "is_emergency": True},
            {"name": "കെ.എസ്.ഇ.ബി ഇലക്ട്രിസിറ്റി ഓഫീസ്", "category": DirectoryEntry.Category.GOVERNMENT_OFFICE, "phone_number": "04712334455", "address_or_stand": "സബ് സ്റ്റേഷൻ റോഡ്", "is_emergency": True},
            {"name": "രാജേഷ് (ഇലക്ട്രീഷ്യൻ & പ്ലംബർ)", "category": DirectoryEntry.Category.ELECTRICIAN, "phone_number": "9847012345", "address_or_stand": "വാർഡ് 3", "is_emergency": False},
            {"name": "മണികണ്ഠൻ (ടാക്സി & ഓട്ടോ സർവീസ്)", "category": DirectoryEntry.Category.TAXI_AUTO, "phone_number": "9446098765", "address_or_stand": "മെയിൻ സ്റ്റാൻഡ്", "is_emergency": False},
        ]
        for d in sample_directory:
            DirectoryEntry.objects.get_or_create(
                name=d["name"],
                defaults={
                    "area": area,
                    "category": d["category"],
                    "phone_number": d["phone_number"],
                    "address_or_stand": d["address_or_stand"],
                    "is_emergency_service": d["is_emergency"],
                    "is_verified": True
                }
            )

        # 6. Seed Sample Event Notice
        EventNotice.objects.get_or_create(
            title="പഞ്ചായത്ത് സൗജന്യ മെഡിക്കൽ & നേത്ര പരിശോധനാ ക്യാമ്പ്",
            defaults={
                "area": area,
                "author": owner,
                "description": "ഈ വരുന്ന ഞായറാഴ്ച രാവിലെ 9 മണി മുതൽ പഞ്ചായത്ത് കമ്മ്യൂണിറ്റി ഹാളിൽ വെച്ച് സൗജന്യ മെഡിക്കൽ ക്യാമ്പ് ഉണ്ടായിരിക്കുന്നതാണ്. എല്ലാവരും പങ്കാളികളാകുക.",
                "category": EventNotice.Category.MEDICAL,
                "venue": "പഞ്ചായത്ത് കമ്മ്യൂണിറ്റി ഹാൾ",
                "is_emergency": False
            }
        )

        # 7. Seed Sample Super Admin User
        admin_user, admin_created = User.objects.get_or_create(
            phone_number="9999999999",
            defaults={
                "full_name": "പ്രധാന അഡ്മിൻ (Super Admin)",
                "role": User.Role.SUPER_ADMIN,
                "area": area,
                "ward_number": 1,
                "is_staff": True,
                "is_superuser": True
            }
        )
        if admin_created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created Super Admin: {admin_user.full_name} (9999999999 / admin123)"))

        # 8. Seed Sample Citizen / Resident User
        citizen_user, citizen_created = User.objects.get_or_create(
            phone_number="9876543219",
            defaults={
                "full_name": "രാഹുൽ കൃഷ്ണൻ (നാട്ടുകാരൻ)",
                "role": User.Role.CITIZEN,
                "area": area,
                "ward_number": 3,
                "address": "കൃഷ്ണ വിലാസം, വാർഡ് 3"
            }
        )
        if citizen_created:
            citizen_user.set_password("pass1234")
            citizen_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created Citizen User: {citizen_user.full_name} (9876543219 / pass1234)"))

        # 9. Seed Sample Order for the Citizen
        sample_shop = Shop.objects.filter(is_verified=True).first()
        if sample_shop and sample_shop.products.exists():
            sample_product = sample_shop.products.first()
            sample_order, order_created = Order.objects.get_or_create(
                customer=citizen_user,
                shop=sample_shop,
                defaults={
                    "status": Order.Status.PENDING,
                    "delivery_type": Order.DeliveryType.STORE_PICKUP,
                    "customer_phone": citizen_user.phone_number,
                    "total_amount": sample_product.price * 2,
                    "notes": "വേഗം തയ്യാറാക്കി വെക്കുക."
                }
            )
            if order_created:
                OrderItem.objects.create(
                    order=sample_order,
                    product=sample_product,
                    product_name=sample_product.name,
                    quantity=2,
                    unit_price=sample_product.price,
                    subtotal=sample_product.price * 2
                )
                self.stdout.write(self.style.SUCCESS(f"Created sample Order #{sample_order.id} for {citizen_user.full_name}"))

        # 10. Seed Sample Complaint from the Citizen
        Complaint.objects.get_or_create(
            citizen=citizen_user,
            title="മെയിൻ ജംഗ്ഷനിലെ സ്ട്രീറ്റ് ലൈറ്റ് കേടാണ്",
            defaults={
                "area": area,
                "description": "ജംഗ്ഷനിൽ കഴിഞ്ഞ 3 ദിവസമായി വെളിച്ചമില്ല. രാത്രിയിൽ യാത്രക്കാർക്ക് ബുദ്ധിമുട്ടാണ്.",
                "category": Complaint.Category.ELECTRICITY,
                "ward_number": 3,
                "location_details": "സെൻട്രൽ ജംഗ്ഷൻ പോസ്റ്റ് നമ്പർ 14",
                "status": Complaint.Status.SUBMITTED
            }
        )

        # 11. Seed Sample Blood Donor
        BloodDonor.objects.get_or_create(
            user=citizen_user,
            defaults={
                "name": citizen_user.full_name,
                "blood_group": BloodDonor.BloodGroup.O_POS,
                "phone_number": citizen_user.phone_number,
                "ward_number": 3,
                "is_available": True
            }
        )

        # 12. Seed Sample Classified Ad
        ClassifiedAd.objects.get_or_create(
            author=citizen_user,
            title="2 BHK വീട് വാടകയ്ക്ക് കൊടുക്കാനുണ്ട്",
            defaults={
                "area": area,
                "ad_type": ClassifiedAd.AdType.RENT,
                "description": "വാർഡ് 3 ൽ മെയിൻ റോഡിനടുത്ത് കാർ പാർക്കിംഗ് സൗകര്യമുള്ള വീട്. നല്ല കുടിവെള്ളം ലഭ്യമാണ്.",
                "contact_phone": citizen_user.phone_number,
                "is_approved": True
            }
        )

        self.stdout.write(self.style.SUCCESS("All village seed data, verified sample shops, orders, and emergency directory created successfully!"))
