"""
Ente Naadu - Shop Progress Tracking & Analytics Engine
Calculates category-aware progress scores, checklist completion,
and performance metrics for Admin & Individual Shop Dashboards.
"""

from decimal import Decimal
from django.db.models import Avg, Count, Q
from apps.shops.models import Shop, Product, Review, ShopCategory
from apps.orders.models import Order, Booking


class ShopProgressCalculator:
    """
    Computes category-aware onboarding & operational progress for a Shop.
    Rules are adapted based on whether the business is product-based or service-based.
    """

    @classmethod
    def calculate_progress(cls, shop: Shop) -> dict:
        """
        Returns a comprehensive dictionary with:
        - overall_percentage: 0 - 100
        - sections: breakdown of each section score and max score
        - checklist: individual items completed vs pending
        - pending_actions: actionable list of missing items
        - metrics: operational counts (orders, bookings, products, reviews)
        - is_service_based: boolean
        - business_type_display: human readable business category
        """
        is_service = shop.is_service_based

        # 1. Section: Basic Profile & Contact Info (Max 20)
        basic_score = 0
        has_core_info = bool(shop.name and shop.contact_phone and shop.address and shop.ward_number)
        if has_core_info:
            basic_score += 10

        has_description = bool(shop.description and len(shop.description.strip()) >= 10)
        if has_description:
            basic_score += 5

        has_media_or_whatsapp = bool(shop.banner_image or shop.whatsapp_number)
        if has_media_or_whatsapp:
            basic_score += 5

        basic_score = min(20, basic_score)

        # 2. Section: Operating Hours & Delivery (Max 15)
        hours_score = 0
        has_hours = bool(shop.opening_time and shop.closing_time) or shop.working_hours.filter(is_closed=False).exists()
        if has_hours:
            hours_score += 10

        if shop.delivery_available or (shop.category and shop.category.interaction_mode):
            hours_score += 5

        hours_score = min(15, hours_score)

        # 3. Section: Location & GPS Geotagging (Max 20)
        location_score = 0
        has_gps = bool(shop.latitude is not None and shop.longitude is not None and float(shop.latitude) != 0.0)
        if has_gps:
            location_score = 20

        # 4. Section: Catalog Readiness - Category Aware (Max 25)
        catalog_score = 0
        products_qs = shop.products.all()
        total_products = products_qs.count()
        available_products = products_qs.filter(is_available=True).count()

        if is_service:
            # Service-based criteria (Parlour, Repair, Barber, etc.)
            if total_products >= 1:
                catalog_score += 10
            if total_products >= 3:
                catalog_score += 10
            has_durations = products_qs.filter(service_duration_minutes__isnull=False).exists()
            if has_durations:
                catalog_score += 5
        else:
            # Product-based criteria (General, Grocery, Bakery, Restaurant, Medical)
            if total_products >= 1:
                catalog_score += 10
            if total_products >= 3:
                catalog_score += 10
            if available_products >= 1:
                catalog_score += 5

        catalog_score = min(25, catalog_score)

        # 5. Section: Admin Verification & Compliance (Max 10)
        verification_score = 10 if shop.is_verified else 0

        # 6. Section: Operations & Community Engagement (Max 10)
        operations_score = 0

        # Check orders & bookings
        orders_qs = Order.objects.filter(shop=shop)
        total_orders = orders_qs.count()
        completed_orders = orders_qs.filter(status=Order.Status.COMPLETED).count()
        pending_orders = orders_qs.filter(status__in=[Order.Status.PENDING, Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY]).count()

        bookings_qs = Booking.objects.filter(shop=shop)
        total_bookings = bookings_qs.count()
        completed_bookings = bookings_qs.filter(status=Booking.Status.COMPLETED).count()
        pending_bookings = bookings_qs.filter(status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED]).count()

        has_operations = (completed_orders > 0 or completed_bookings > 0)
        if has_operations:
            operations_score += 5

        reviews_qs = shop.reviews.all()
        reviews_count = reviews_qs.count()
        avg_rating_val = reviews_qs.aggregate(Avg('rating'))['rating__avg']
        average_rating = round(float(avg_rating_val), 1) if avg_rating_val else None

        if reviews_count > 0:
            operations_score += 5

        operations_score = min(10, operations_score)

        # Total Calculation
        total_percentage = basic_score + hours_score + location_score + catalog_score + verification_score + operations_score
        total_percentage = max(0, min(100, total_percentage))

        # Checklist Items
        checklist = [
            {
                "id": "basic_info",
                "title": "അടിസ്ഥാന വിവരങ്ങൾ (Shop Profile)",
                "description": "പേര്, വിലാസം, വാർഡ് നമ്പർ, ഫോൺ നമ്പർ എന്നിവ",
                "is_completed": has_core_info,
                "weight": 10,
                "category": "profile",
            },
            {
                "id": "description",
                "title": "സ്ഥാപനത്തിന്റെ വിവരണം (Shop Bio)",
                "description": "കടയെക്കുറിച്ചുള്ള ലഘു വിവരണം",
                "is_completed": has_description,
                "weight": 5,
                "category": "profile",
            },
            {
                "id": "hours",
                "title": "പ്രവർത്തന സമയം (Opening Hours)",
                "description": "തുറക്കുന്നതും അടയ്ക്കുന്നതുമായ സമയം",
                "is_completed": has_hours,
                "weight": 10,
                "category": "operations",
            },
            {
                "id": "location",
                "title": "GPS മാപ്പ് ലൊക്കേഷൻ (Geotagged Location)",
                "description": "ഓപ്പൺസ്ട്രീറ്റ്മാപ്പിൽ കട കൃത്യമായി അടയാളപ്പെടുത്തുക",
                "is_completed": has_gps,
                "weight": 20,
                "category": "location",
            },
            {
                "id": "catalog",
                "title": "സേവനങ്ങൾ / ഉൽപ്പന്നങ്ങൾ (Products / Services)",
                "description": "കുറഞ്ഞത് 3 ഉൽപ്പന്നങ്ങൾ അല്ലെങ്കിൽ സേവനങ്ങൾ ലിസ്റ്റ് ചെയ്യുക" if not is_service else "കുറഞ്ഞത് 3 സേവനങ്ങൾ സമയദൈർഘ്യത്തോടെ ലിസ്റ്റ് ചെയ്യുക",
                "is_completed": (total_products >= 3),
                "weight": 20,
                "category": "catalog",
            },
            {
                "id": "verification",
                "title": "അഡ്മിൻ പരിശോധന (Admin Verification)",
                "description": "പഞ്ചായത്ത് അഡ്മിൻ നേരിട്ട് പരിശോധിച്ച് നൽകുന്ന അംഗീകാരം",
                "is_completed": shop.is_verified,
                "weight": 10,
                "category": "verification",
            },
            {
                "id": "reviews",
                "title": "ഉപഭോക്തൃ റിവ്യൂകൾ (Customer Reviews)",
                "description": "നാട്ടുകാരുടെ പരിശോധിച്ച റിവ്യൂകളും റേറ്റിംഗും",
                "is_completed": (reviews_count > 0),
                "weight": 5,
                "category": "trust",
            },
        ]

        # Actionable Pending Steps
        pending_actions = []
        if not has_gps:
            pending_actions.append({
                "type": "location",
                "title": "GPS ലൊക്കേഷൻ ചേർക്കുക",
                "action_url": f"/dashboard/shop/{shop.id}/location/",
                "urgency": "high",
                "message": "നാട്ടുകാർക്ക് സമീപത്തെ കടകൾ കണ്ടെത്താൻ GPS നിർബന്ധമാണ്."
            })
        if not has_hours:
            pending_actions.append({
                "type": "hours",
                "title": "പ്രവർത്തന സമയം ചേർക്കുക",
                "action_url": f"/dashboard/shop/{shop.id}/hours/",
                "urgency": "medium",
                "message": "കട തുറക്കുന്നതും അടയ്ക്കുന്നതുമായ സമയം കൃത്യമായി നൽകുക."
            })
        if total_products < 3:
            pending_actions.append({
                "type": "catalog",
                "title": "സേവനങ്ങൾ / ഉൽപ്പന്നങ്ങൾ ലിസ്റ്റ് ചെയ്യുക",
                "action_url": f"/dashboard/shop/{shop.id}/product/add/",
                "urgency": "high",
                "message": f"നിലവിൽ {total_products} ഇനങ്ങൾ മാത്രം. കുറഞ്ഞത് 3 എണ്ണം ചേർക്കുക."
            })
        if not shop.is_verified:
            pending_actions.append({
                "type": "verification",
                "title": "അഡ്മിൻ അപ്രൂവൽ കാത്തിരിക്കുന്നു",
                "action_url": "#",
                "urgency": "medium",
                "message": "വിവരങ്ങൾ നൽകിയ ശേഷം അഡ്മിൻ പരിശോധിച്ച് വേരിഫൈ ചെയ്യും."
            })
        if not has_media_or_whatsapp:
            pending_actions.append({
                "type": "media",
                "title": "ബാനർ ഫോട്ടോ അല്ലെങ്കിൽ WhatsApp നമ്പർ ചേർക്കുക",
                "action_url": "/dashboard/shop/",
                "urgency": "low",
                "message": "കടയുടെ ആകർഷകമായ ഫോട്ടോയും വാട്ട്സാപ്പ് നമ്പറും ചേർക്കുക."
            })

        return {
            "shop_id": shop.id,
            "shop_name": shop.name,
            "owner_name": shop.owner.full_name or shop.owner.phone_number,
            "category_name": shop.category.name if shop.category else "ജനറൽ",
            "business_type": shop.business_type,
            "is_service_based": is_service,
            "ward_number": shop.ward_number,
            "is_verified": shop.is_verified,
            "is_open": shop.is_open,
            "created_at": shop.created_at,
            "overall_percentage": total_percentage,
            "sections": {
                "profile": {"score": basic_score, "max": 20, "percentage": int((basic_score / 20) * 100)},
                "hours": {"score": hours_score, "max": 15, "percentage": int((hours_score / 15) * 100)},
                "location": {"score": location_score, "max": 20, "percentage": int((location_score / 20) * 100)},
                "catalog": {"score": catalog_score, "max": 25, "percentage": int((catalog_score / 25) * 100)},
                "verification": {"score": verification_score, "max": 10, "percentage": int((verification_score / 10) * 100)},
                "operations": {"score": operations_score, "max": 10, "percentage": int((operations_score / 10) * 100)},
            },
            "metrics": {
                "total_products": total_products,
                "available_products": available_products,
                "total_orders": total_orders,
                "completed_orders": completed_orders,
                "pending_orders": pending_orders,
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "pending_bookings": pending_bookings,
                "reviews_count": reviews_count,
                "average_rating": average_rating,
            },
            "checklist": checklist,
            "pending_actions": pending_actions,
        }

    @classmethod
    def get_admin_summary(cls, queryset=None) -> dict:
        """
        Computes aggregate progress metrics across all registered shops for Super Admin.
        Includes distribution by progress ranges, category averages, and pending actions summary.
        """
        if queryset is None:
            queryset = Shop.objects.all().select_related('category', 'owner', 'area')

        total_shops = queryset.count()
        if total_shops == 0:
            return {
                "total_shops": 0,
                "verified_shops": 0,
                "unverified_shops": 0,
                "average_progress": 0,
                "distribution": {"high": 0, "medium": 0, "low": 0},
                "category_stats": [],
                "shops_progress": [],
            }

        shops_progress = [cls.calculate_progress(s) for s in queryset]

        total_progress_sum = sum(sp['overall_percentage'] for sp in shops_progress)
        avg_progress = round(total_progress_sum / total_shops, 1)

        verified_count = sum(1 for sp in shops_progress if sp['is_verified'])
        unverified_count = total_shops - verified_count

        # Distribution: High (>=80%), Medium (50-79%), Low (<50%)
        high_progress = sum(1 for sp in shops_progress if sp['overall_percentage'] >= 80)
        medium_progress = sum(1 for sp in shops_progress if 50 <= sp['overall_percentage'] < 80)
        low_progress = sum(1 for sp in shops_progress if sp['overall_percentage'] < 50)

        # Category-wise averages
        from collections import defaultdict
        cat_map = defaultdict(list)
        for sp in shops_progress:
            cat_map[sp['category_name']].append(sp['overall_percentage'])

        category_stats = [
            {
                "category": cat_name,
                "count": len(scores),
                "avg_progress": round(sum(scores) / len(scores), 1)
            }
            for cat_name, scores in sorted(cat_map.items())
        ]

        return {
            "total_shops": total_shops,
            "verified_shops": verified_count,
            "unverified_shops": unverified_count,
            "average_progress": avg_progress,
            "distribution": {
                "high": high_progress,
                "medium": medium_progress,
                "low": low_progress,
            },
            "category_stats": category_stats,
            "shops_progress": shops_progress,
        }
