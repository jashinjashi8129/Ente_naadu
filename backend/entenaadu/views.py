from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.db.models import Q, Count
from decimal import Decimal
from datetime import datetime, date

from apps.accounts.models import User, Area, UserLocation, AuditLog
from apps.common.geo import is_valid_coord, haversine_distance, get_bounding_box
from apps.common.audit import log_audit
from apps.common.notifications import (
    notify_order_created,
    notify_order_status_changed,
    notify_booking_requested,
    notify_booking_status_changed,
    notify_directory_status,
    notify_complaint_status
)
from apps.shops.models import (
    Shop,
    ShopCategory,
    Product,
    Review,
    ShopWorkingHour,
    RatingCriterion,
    ReviewCriterionRating
)
from apps.shops.services import ShopProgressCalculator
from apps.orders.models import Order, OrderItem, Cart, CartItem, Booking
from apps.events.models import EventNotice
from apps.complaints.models import Complaint
from apps.directory.models import DirectoryEntry, BloodDonor, ClassifiedAd


@ensure_csrf_cookie
def home_view(request):
    """
    Modern 3D Village Web Portal served directly via Django templates at ₹0 cost.
    """
    total_shops = Shop.objects.filter(is_verified=True).count()
    open_shops = Shop.objects.filter(is_verified=True, is_open=True).count()
    all_categories = ShopCategory.objects.all().order_by('name')
    categories = all_categories[:12]
    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:3]
    latest_events = EventNotice.objects.filter(is_emergency=False)[:6]
    recent_shops = Shop.objects.filter(is_verified=True).select_related('category', 'area').order_by('-is_open', '-created_at')[:8]
    emergency_directory = DirectoryEntry.objects.filter(is_verified=True, is_emergency_service=True)[:6]
    service_directory = DirectoryEntry.objects.filter(is_verified=True, is_emergency_service=False)[:6]
    blood_donors_count = BloodDonor.objects.filter(is_available=True).count()
    recent_donors = BloodDonor.objects.filter(is_available=True).order_by('?')[:6]
    recent_classifieds = ClassifiedAd.objects.filter(is_approved=True)[:4]
    all_areas = Area.objects.filter(is_active=True).order_by('name')

    context = {
        'total_shops': total_shops,
        'open_shops': open_shops,
        'categories': categories,
        'all_categories': all_categories,
        'all_areas': all_areas,
        'emergency_alerts': emergency_alerts,
        'latest_events': latest_events,
        'recent_shops': recent_shops,
        'emergency_directory': emergency_directory,
        'service_directory': service_directory,
        'directory_categories': DirectoryEntry.Category.choices,
        'blood_donors_count': blood_donors_count,
        'recent_donors': recent_donors,
        'recent_classifieds': recent_classifieds,
    }
    return render(request, 'index.html', context)


# ==============================================================================
# SHOP DISCOVERY & SHOP DETAIL VIEWS
# ==============================================================================

_distinct_owners_synced = False

def _ensure_distinct_shop_owners():
    """
    Auto-corrects sample shops so that each shop has its own dedicated, distinct owner account
    in development/production databases. This immediately solves the issue where multiple shops
    shared the same owner account from initial seeds.
    """
    global _distinct_owners_synced
    if _distinct_owners_synced:
        return
    _distinct_owners_synced = True

    try:
        sample_owner_specs = [
            ("നാട്ടുപീടിക", "9876543210", "സുരേഷ് കുമാർ (പലചരക്ക്)"),
            ("മലബാർ", "9876543211", "ഫൈസൽ റഹ്മാൻ (ഹോട്ടൽ)"),
            ("ഗ്രീൻ വാലി", "9876543214", "തോമസ് വർഗ്ഗീസ് (ബേക്കറി)"),
            ("ഫ്രഷ് നാടൻ", "9876543215", "രാധാകൃഷ്ണൻ നായർ (പച്ചക്കറി)"),
            ("പച്ചക്കറി", "9876543215", "രാധാകൃഷ്ണൻ നായർ (പച്ചക്കറി)"),
            ("റോയൽ", "9876543212", "മനോജ് കുമാർ (സലൂൺ)"),
            ("ജീവൻ", "9876543213", "ഡോ. പ്രദീപ് കുമാർ (ഫാർമസി)"),
            ("ലക്ഷ്മി", "9876543216", "ലക്ഷ്മി പ്രിയ (ബ്യൂട്ടി പാർലർ)"),
        ]
        area = Area.objects.filter(is_active=True).first()
        for kw, phone, name in sample_owner_specs:
            matched_shops = Shop.objects.filter(name__icontains=kw)
            for s in matched_shops:
                target_owner, created = User.objects.get_or_create(
                    phone_number=phone,
                    defaults={
                        'full_name': name,
                        'role': User.Role.SHOP_OWNER,
                        'area': area or s.area,
                        'ward_number': s.ward_number,
                        'address': s.address,
                        'is_staff': False,
                        'is_superuser': False,
                    }
                )
                if created:
                    target_owner.set_password('pass1234')
                    target_owner.save()
                elif target_owner.is_staff or target_owner.is_superuser:
                    if target_owner.phone_number != '9999999999':
                        target_owner.is_staff = False
                        target_owner.is_superuser = False
                        target_owner.save(update_fields=['is_staff', 'is_superuser'])
                if s.owner_id != target_owner.id:
                    s.owner = target_owner
                    s.save(update_fields=['owner'])
    except Exception:
        pass


@ensure_csrf_cookie
def shop_list_view(request):
    """
    Browse and search local community shops with filters (category, ward, open/closed, delivery).
    """
    _ensure_distinct_shop_owners()
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    business_type = request.GET.get('type', '').strip()
    ward_filter = request.GET.get('ward', '').strip()
    open_only = request.GET.get('open_now') == '1'
    delivery_only = request.GET.get('delivery') == '1'
    view_scope = request.GET.get('scope', '').strip()  # 'other' or empty

    # Public directory lists verified shops
    shops = Shop.objects.filter(is_verified=True).select_related('category', 'area')

    # If logged-in shop owner requests "other" shops, exclude their own shops
    my_shop = None
    if request.user.is_authenticated and request.user.role == User.Role.SHOP_OWNER:
        my_shop = Shop.objects.filter(owner=request.user).first()
        if view_scope == 'other':
            shops = shops.exclude(owner=request.user)

    if query:
        shops = shops.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(todays_offer__icontains=query)
        )

    if category_id and category_id.isdigit():
        shops = shops.filter(category_id=int(category_id))

    if business_type:
        shops = shops.filter(category__business_type=business_type)

    if ward_filter and ward_filter.isdigit():
        shops = shops.filter(ward_number=int(ward_filter))

    if open_only:
        shops = shops.filter(is_open=True)

    if delivery_only:
        shops = shops.filter(delivery_available=True)

    shops = shops.order_by('-is_open', 'name')
    all_categories = ShopCategory.objects.all().order_by('name')
    all_areas = Area.objects.filter(is_active=True).order_by('name')
    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:2]
    ward_numbers = list(range(1, 21))
    business_types = ShopCategory.BusinessType.choices

    context = {
        'shops': shops,
        'total_count': shops.count(),
        'all_categories': all_categories,
        'all_areas': all_areas,
        'ward_numbers': ward_numbers,
        'business_types': business_types,
        'selected_type': business_type,
        'query': query,
        'selected_category': int(category_id) if category_id and category_id.isdigit() else None,
        'selected_ward': int(ward_filter) if ward_filter and ward_filter.isdigit() else None,
        'open_only': open_only,
        'delivery_only': delivery_only,
        'view_scope': view_scope,
        'my_shop': my_shop,
        'emergency_alerts': emergency_alerts,
    }
    return render(request, 'shops/shop_list.html', context)


@ensure_csrf_cookie
def shop_detail_view(request, shop_id):
    """
    Detailed shop page with products, live open status, order creation modal, and contact actions.
    Server-side ownership verification: separates public shop details from management controls.
    """
    _ensure_distinct_shop_owners()
    shop = get_object_or_404(Shop.objects.select_related('owner', 'category', 'area'), id=shop_id, is_verified=True)
    products = shop.products.all().order_by('-is_available', 'name')
    reviews = shop.reviews.select_related('user').order_by('-created_at')[:8]
    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:2]
    all_areas = Area.objects.filter(is_active=True).order_by('name')
    all_categories = ShopCategory.objects.all().order_by('name')

    # Server-verified management permission:
    # A shop can ONLY be managed by its actual owner on this public detail page.
    is_owner = request.user.is_authenticated and (shop.owner_id == request.user.id)
    can_manage_shop = is_owner

    has_gps = bool(shop.latitude and shop.longitude)
    directions_url = f"https://www.google.com/maps/dir/?api=1&destination={shop.latitude},{shop.longitude}" if has_gps else None

    # Working hours and real-time business status
    business_status = shop.get_business_status()
    weekly_schedule = shop.get_weekly_schedule()

    # Category-Based Rating System Summary & Criteria
    rating_summary = shop.get_rating_summary()
    rating_criteria = shop.get_rating_criteria()

    user_can_review = False
    user_review = None
    eligible_orders = []
    eligible_bookings = []

    if request.user.is_authenticated and not is_owner:
        user_review = Review.objects.filter(shop=shop, user=request.user).first()
        if not user_review:
            eligible_orders = Order.objects.filter(
                customer=request.user,
                shop=shop,
                status=Order.Status.COMPLETED
            ).exclude(reviews__isnull=False)

            eligible_bookings = Booking.objects.filter(
                customer=request.user,
                shop=shop,
                status=Booking.Status.COMPLETED
            ).exclude(reviews__isnull=False)

            user_can_review = eligible_orders.exists() or eligible_bookings.exists()

    context = {
        'shop': shop,
        'products': products,
        'reviews': reviews,
        'rating_summary': rating_summary,
        'rating_criteria': rating_criteria,
        'user_can_review': user_can_review,
        'user_review': user_review,
        'eligible_orders': eligible_orders,
        'eligible_bookings': eligible_bookings,
        'emergency_alerts': emergency_alerts,
        'all_areas': all_areas,
        'all_categories': all_categories,
        'is_shop_owner': is_owner,
        'can_manage_shop': can_manage_shop,
        'today': date.today().strftime('%Y-%m-%d'),
        'is_beauty_parlour': shop.is_beauty_parlour,
        'is_service_based': shop.is_service_based,
        'is_product_based': shop.is_product_based,
        'has_gps_location': has_gps,
        'directions_url': directions_url,
        'business_status': business_status,
        'weekly_schedule': weekly_schedule,
    }
    return render(request, 'shops/shop_detail.html', context)


# ==============================================================================
# CITIZEN / USER DASHBOARD
# ==============================================================================

@login_required(login_url='web-login')
def user_dashboard_view(request):
    """
    Personalized citizen dashboard showing past orders, bookings, complaint tracking, and quick actions.
    """
    user = request.user
    user_orders_qs = Order.objects.filter(customer=user)
    pending_orders_count = user_orders_qs.filter(
        status__in=[Order.Status.PENDING, Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY]
    ).count()
    completed_orders_count = user_orders_qs.filter(status=Order.Status.COMPLETED).count()
    orders = user_orders_qs.select_related('shop').prefetch_related('items__product').order_by('-created_at')[:20]

    user_bookings = Booking.objects.filter(customer=user).select_related('shop', 'service').order_by('-booking_date', '-created_at')[:20]

    # Category-Based Rating tracking for citizen dashboard
    reviewed_order_ids = set(Review.objects.filter(user=user, order__isnull=False).values_list('order_id', flat=True))
    reviewed_booking_ids = set(Review.objects.filter(user=user, booking__isnull=False).values_list('booking_id', flat=True))
    reviewed_shop_ids = set(Review.objects.filter(user=user).values_list('shop_id', flat=True))

    complaints = Complaint.objects.filter(citizen=user).order_by('-created_at')[:10]
    user_directory_entries = DirectoryEntry.objects.filter(submitted_by=user).order_by('-created_at')
    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:2]
    all_areas = Area.objects.filter(is_active=True).order_by('name')
    all_categories = ShopCategory.objects.all().order_by('name')

    context = {
        'user': user,
        'orders': orders,
        'bookings': user_bookings,
        'reviewed_order_ids': reviewed_order_ids,
        'reviewed_booking_ids': reviewed_booking_ids,
        'reviewed_shop_ids': reviewed_shop_ids,
        'complaints': complaints,
        'user_directory_entries': user_directory_entries,
        'directory_categories': DirectoryEntry.Category.choices,
        'pending_orders_count': pending_orders_count,
        'completed_orders_count': completed_orders_count,
        'emergency_alerts': emergency_alerts,
        'all_areas': all_areas,
        'all_categories': all_categories,
    }
    return render(request, 'dashboard/user_dashboard.html', context)


# ==============================================================================
# SHOP OWNER DASHBOARD
# ==============================================================================

def _safe_ensure_migrations():
    """Ensure pending migrations are automatically applied if schema is out of sync."""
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
    except Exception as e:
        print(f"[Auto-Migrate]: {e}")


@login_required(login_url='web-login')
def shop_dashboard_view(request):
    """
    Shop business management portal: open/closed switch, services/product catalog, incoming orders & bookings.
    """
    _ensure_distinct_shop_owners()
    user = request.user
    shop = Shop.objects.filter(owner=user).select_related('category', 'area').first()

    if not shop:
        messages.info(request, "നിങ്ങൾ ഇതുവരെ കടയൊന്നും രജിസ്റ്റർ ചെയ്തിട്ടില്ല. ദയവായി കട രജിസ്റ്റർ ചെയ്യുക.")
        return redirect('home')

    try:
        products = list(shop.products.all().order_by('-is_available', 'name'))
    except Exception as e:
        if 'no such column' in str(e) or 'no such table' in str(e):
            _safe_ensure_migrations()
            products = list(shop.products.all().order_by('-is_available', 'name'))
        else:
            raise

    shop_orders_qs = Order.objects.filter(shop=shop)
    pending_orders_count = shop_orders_qs.filter(status=Order.Status.PENDING).count()
    active_orders_count = shop_orders_qs.filter(
        status__in=[Order.Status.ACCEPTED, Order.Status.PREPARING, Order.Status.READY]
    ).count()
    completed_orders_count = shop_orders_qs.filter(status=Order.Status.COMPLETED).count()
    orders = shop_orders_qs.select_related('customer').prefetch_related('items__product').order_by('-created_at')[:30]

    # Appointments / Bookings (for Parlours, Salons & Service providers)
    bookings_qs = Booking.objects.filter(shop=shop)
    pending_bookings_count = bookings_qs.filter(status=Booking.Status.PENDING).count()
    confirmed_bookings_count = bookings_qs.filter(status=Booking.Status.CONFIRMED).count()
    completed_bookings_count = bookings_qs.filter(status=Booking.Status.COMPLETED).count()
    bookings = bookings_qs.select_related('customer', 'service').order_by('-booking_date', '-created_at')[:30]

    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:2]
    all_areas = Area.objects.filter(is_active=True).order_by('name')
    all_categories = ShopCategory.objects.all().order_by('name')

    # Calculate real-time category-aware progress
    shop_progress = shop.get_progress()

    context = {
        'shop': shop,
        'orders': orders,
        'products': products,
        'bookings': bookings,
        'pending_orders_count': pending_orders_count,
        'active_orders_count': active_orders_count,
        'completed_orders_count': completed_orders_count,
        'pending_bookings_count': pending_bookings_count,
        'confirmed_bookings_count': confirmed_bookings_count,
        'completed_bookings_count': completed_bookings_count,
        'is_beauty_parlour': shop.is_beauty_parlour,
        'is_service_based': shop.is_service_based,
        'shop_progress': shop_progress,
        'emergency_alerts': emergency_alerts,
        'all_areas': all_areas,
        'all_categories': all_categories,
    }
    return render(request, 'dashboard/shop_dashboard.html', context)


# ==============================================================================
# SINGLE SUPER ADMIN DASHBOARD
# ==============================================================================

@login_required(login_url='web-login')
def admin_dashboard_view(request):
    """
    Exclusive management console for the single Super Admin:
    Approve shops, moderate complaints, issue emergency notices, monitor metrics,
    and inspect overall shop onboarding & verification progress.
    """
    user = request.user
    if not (user.is_staff or user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അഡ്മിന്മാർക്ക് മാത്രമേ ഈ പേജിൽ പ്രവേശനമുള്ളൂ.")
        return redirect('home')

    pending_shops = Shop.objects.filter(is_verified=False).select_related('owner', 'category', 'area').order_by('-created_at')
    pending_directory_entries = DirectoryEntry.objects.filter(is_verified=False).select_related('submitted_by', 'area').order_by('-created_at')
    active_complaints_qs = Complaint.objects.filter(
        status__in=[Complaint.Status.SUBMITTED, Complaint.Status.UNDER_REVIEW, Complaint.Status.IN_PROGRESS]
    )
    open_complaints_count = active_complaints_qs.count()
    active_complaints = active_complaints_qs.select_related('citizen', 'area').order_by('-created_at')[:20]
    recent_notices = EventNotice.objects.all().order_by('-created_at')[:10]

    # Metrics
    metrics = {
        'total_citizens': User.objects.filter(role=User.Role.CITIZEN).count(),
        'total_shops': Shop.objects.filter(is_verified=True).count(),
        'pending_shops_count': pending_shops.count(),
        'pending_directory_count': pending_directory_entries.count(),
        'open_complaints_count': open_complaints_count,
        'total_orders': Order.objects.count(),
        'total_donors': BloodDonor.objects.count(),
    }

    # Aggregate shop progress metrics
    admin_progress_summary = ShopProgressCalculator.get_admin_summary()

    all_areas = Area.objects.filter(is_active=True).order_by('name')
    all_categories = ShopCategory.objects.all().order_by('name')
    emergency_alerts = EventNotice.objects.filter(is_emergency=True)[:2]

    context = {
        'pending_shops': pending_shops,
        'pending_directory_entries': pending_directory_entries,
        'active_complaints': active_complaints,
        'recent_notices': recent_notices,
        'metrics': metrics,
        'admin_progress_summary': admin_progress_summary,
        'all_areas': all_areas,
        'all_categories': all_categories,
        'emergency_alerts': emergency_alerts,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


# ==============================================================================
# PROGRESS TRACKING VIEWS (Admin & Individual Shop)
# ==============================================================================

@login_required(login_url='web-login')
def web_shop_progress_view(request, shop_id):
    """
    Dedicated Progress Tracking & Optimization Dashboard for an individual shop.
    Security: Strict ownership check. Shop owners can ONLY see their own shop.
    Admins can view any shop's progress. Customer private data is never exposed.
    """
    shop = _get_manageable_shop_or_403(request.user, shop_id)
    progress_data = shop.get_progress()

    context = {
        'shop': shop,
        'progress': progress_data,
        'sections': progress_data['sections'],
        'metrics': progress_data['metrics'],
        'checklist': progress_data['checklist'],
        'pending_actions': progress_data['pending_actions'],
    }
    return render(request, 'dashboard/shop_progress_detail.html', context)


@login_required(login_url='web-login')
def web_admin_shops_progress_view(request):
    """
    Dedicated Admin Portal for tracking progress across all registered shops.
    Features:
    - Search by shop name, owner name, contact number
    - Category filter & Ward filter
    - Verification status filter
    - Progress tier filter (High >=80%, Medium 50-79%, Low <50%)
    - Comparison table with progress bars and quick actions
    """
    user = request.user
    if not (user.is_staff or user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അഡ്മിന്മാർക്ക് മാത്രമേ ഈ പേജിൽ പ്രവേശനമുള്ളൂ.")
        return redirect('home')

    qs = Shop.objects.all().select_related('category', 'owner', 'area')

    # Query Filters
    search_q = request.GET.get('q', '').strip()
    if search_q:
        qs = qs.filter(
            Q(name__icontains=search_q) |
            Q(owner__full_name__icontains=search_q) |
            Q(owner__phone_number__icontains=search_q) |
            Q(contact_phone__icontains=search_q) |
            Q(address__icontains=search_q)
        )

    category_id = request.GET.get('category', '').strip()
    if category_id and category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))

    ward = request.GET.get('ward', '').strip()
    if ward and ward.isdigit():
        qs = qs.filter(ward_number=int(ward))

    is_verified = request.GET.get('verified', '').strip()
    if is_verified in ['true', '1', 'yes']:
        qs = qs.filter(is_verified=True)
    elif is_verified in ['false', '0', 'no']:
        qs = qs.filter(is_verified=False)

    # Sort options
    sort_by = request.GET.get('sort', 'name')
    if sort_by == 'newest':
        qs = qs.order_by('-created_at')
    elif sort_by == 'oldest':
        qs = qs.order_by('created_at')
    elif sort_by == 'ward':
        qs = qs.order_by('ward_number', 'name')
    else:
        qs = qs.order_by('name')

    summary = ShopProgressCalculator.get_admin_summary(qs)
    shops_progress = summary['shops_progress']

    # Filter by progress tier in memory if requested
    tier = request.GET.get('tier', '').strip()
    if tier == 'high':
        shops_progress = [s for s in shops_progress if s['overall_percentage'] >= 80]
    elif tier == 'medium':
        shops_progress = [s for s in shops_progress if 50 <= s['overall_percentage'] < 80]
    elif tier == 'low':
        shops_progress = [s for s in shops_progress if s['overall_percentage'] < 50]

    all_categories = ShopCategory.objects.all().order_by('name')
    all_wards = sorted(list(set(Shop.objects.values_list('ward_number', flat=True))))

    context = {
        'summary': summary,
        'shops_progress': shops_progress,
        'all_categories': all_categories,
        'all_wards': all_wards,
        'search_q': search_q,
        'selected_category': category_id,
        'selected_ward': ward,
        'selected_verified': is_verified,
        'selected_tier': tier,
        'selected_sort': sort_by,
        'total_filtered_count': len(shops_progress),
    }
    return render(request, 'dashboard/admin_shops_progress.html', context)


# ==============================================================================
# WEB FORM ACTIONS (Safe, Atomic, Protected)
# ==============================================================================

def _get_manageable_product_or_403(user, product_id):
    """
    Retrieves a product only if the authenticated user owns the shop,
    or has superuser privileges (anti-BOLA / IDOR protection).
    Shop owners can NEVER modify or delete another shop's products.
    """
    if not user.is_authenticated:
        raise PermissionDenied("ഈ പ്രവർത്തനം നടത്താൻ നിങ്ങൾ ലോഗിൻ ചെയ്യണം.")
    product = get_object_or_404(Product.objects.select_related('shop', 'shop__owner'), id=product_id)
    is_owner = (product.shop.owner_id == user.id)
    is_superadmin = (user.role == User.Role.SUPER_ADMIN or getattr(user, 'is_superuser', False))
    if not (is_owner or is_superadmin):
        raise PermissionDenied("മറ്റൊരു കടയിലെ ഉൽപ്പന്നം കൈകാര്യം ചെയ്യാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
    return product


def _get_manageable_shop_or_403(user, shop_id):
    """
    Retrieves a shop only if the authenticated user owns it,
    or has superuser privileges.
    Shop owners can NEVER modify another shop.
    """
    if not user.is_authenticated:
        raise PermissionDenied("ഈ പ്രവർത്തനം നടത്താൻ നിങ്ങൾ ലോഗിൻ ചെയ്യണം.")
    shop = get_object_or_404(Shop.objects.select_related('owner'), id=shop_id)
    is_owner = (shop.owner_id == user.id)
    is_superadmin = (user.role == User.Role.SUPER_ADMIN or getattr(user, 'is_superuser', False))
    if not (is_owner or is_superadmin):
        raise PermissionDenied("ഈ കടയിൽ മാറ്റങ്ങൾ വരുത്താൻ നിങ്ങൾക്ക് അധികാരമില്ല.")
    return shop


@login_required(login_url='web-login')
def web_shop_toggle_open(request, shop_id):
    """
    Toggles the open/closed state or emergency temporary closure of the shop by its authenticated owner.
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    shop = _get_manageable_shop_or_403(request.user, shop_id)

    if shop.is_temporarily_closed:
        shop.is_temporarily_closed = False
        shop.is_open = True
        shop.save(update_fields=['is_temporarily_closed', 'is_open'])
        messages.success(request, "കടയുടെ താൽക്കാലിക അവധി മാറ്റി സാധാരണ പ്രവർത്തന ഷെഡ്യൂളിലേക്ക് മാറ്റി.")
    else:
        shop.is_temporarily_closed = True
        shop.is_open = False
        reason = request.POST.get('reason', '').strip()
        if reason:
            shop.temporary_close_reason = reason
            shop.save(update_fields=['is_temporarily_closed', 'is_open', 'temporary_close_reason'])
        else:
            shop.save(update_fields=['is_temporarily_closed', 'is_open'])
        messages.success(request, "കട താൽക്കാലികമായി അടച്ചതായി രേഖപ്പെടുത്തി (Temporarily Closed).")
    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_product_create(request, shop_id):
    """
    Allows shop owner to add a product or service item.
    Enforces strict ownership: shop.owner must equal request.user.
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    shop = _get_manageable_shop_or_403(request.user, shop_id)

    name = request.POST.get('name', '').strip()
    price = request.POST.get('price', '').strip()
    discount_price = request.POST.get('discount_price', '').strip()
    duration_str = (request.POST.get('service_duration_minutes') or request.POST.get('duration_minutes') or '').strip()
    unit = request.POST.get('unit', '').strip()
    description = request.POST.get('description', '').strip()
    requires_prescription = request.POST.get('requires_prescription') == 'on'
    expiry_info = request.POST.get('expiry_info', '').strip()
    image_file = request.FILES.get('image')

    parsed_duration = None
    if duration_str:
        try:
            parsed_duration = int(duration_str)
            if parsed_duration <= 0:
                parsed_duration = None
        except ValueError:
            parsed_duration = None

    if not unit:
        if parsed_duration:
            unit = f"{parsed_duration} മിനിറ്റ്"
        elif shop.is_service_based:
            unit = "സേവനം"
        else:
            unit = '1 unit'

    if not name or not price:
        item_label = "സേവനത്തിന്റെ" if shop.is_service_based else "ഉൽപ്പന്നത്തിന്റെ"
        messages.error(request, f"{item_label} പേരും വിലയും നൽകണം.")
        return redirect('shop-dashboard')

    try:
        parsed_price = Decimal(price)
        if parsed_price < 0:
            messages.error(request, "വില പൂജ്യത്തിൽ താഴെയാകാൻ പാടില്ല.")
            return redirect('shop-dashboard')

        parsed_discount = Decimal(discount_price) if discount_price else None
        if parsed_discount is not None and parsed_discount < 0:
            messages.error(request, "ഓഫർ വില പൂജ്യത്തിൽ താഴെയാകാൻ പാടില്ല.")
            return redirect('shop-dashboard')

        new_prod = Product.objects.create(
            shop=shop,
            name=name,
            price=parsed_price,
            discount_price=parsed_discount,
            unit=unit,
            service_duration_minutes=parsed_duration,
            description=description,
            requires_prescription=requires_prescription,
            expiry_info=expiry_info,
            is_available=True,
            image=image_file if image_file else None
        )
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.PRODUCT_CREATE,
            target_type='Product',
            target_id=new_prod.id,
            target_identifier=new_prod.name,
            reason=f"Added to shop {shop.name}"
        )
        item_label = "സേവനം" if shop.is_service_based else "ഉൽപ്പന്നം"
        messages.success(request, f"'{name}' വിജയകരമായി {item_label} കാറ്റലോഗിൽ ചേർത്തു.")
    except Exception as e:
        messages.error(request, f"ചേർക്കുന്നതിൽ പിശക്: {e}")

    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_product_edit(request, product_id):
    """
    Allows shop owner to edit an existing product or service details.
    Enforces strict ownership: product.shop.owner must equal request.user.
    """
    product = _get_manageable_product_or_403(request.user, product_id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price = request.POST.get('price', '').strip()
        discount_price = request.POST.get('discount_price', '').strip()
        duration_str = (request.POST.get('service_duration_minutes') or request.POST.get('duration_minutes') or '').strip()
        unit = request.POST.get('unit', '').strip()
        description = request.POST.get('description', '').strip()
        requires_prescription = request.POST.get('requires_prescription') == 'on'
        expiry_info = request.POST.get('expiry_info', '').strip()
        is_available = request.POST.get('is_available') in ['on', 'true', '1']

        if not name or not price:
            messages.error(request, "പേരും വിലയും നൽകണം.")
            return redirect('shop-dashboard')

        try:
            parsed_price = Decimal(price)
            if parsed_price < 0:
                messages.error(request, "വില പൂജ്യത്തിൽ താഴെയാകാൻ പാടില്ല.")
                return redirect('shop-dashboard')

            parsed_discount = Decimal(discount_price) if discount_price else None
            if parsed_discount is not None and parsed_discount < 0:
                messages.error(request, "ഓഫർ വില പൂജ്യത്തിൽ താഴെയാകാൻ പാടില്ല.")
                return redirect('shop-dashboard')

            product.name = name
            product.price = parsed_price
            product.discount_price = parsed_discount
            if unit:
                product.unit = unit

            if duration_str:
                try:
                    product.service_duration_minutes = int(duration_str)
                except ValueError:
                    pass
            elif 'service_duration_minutes' in request.POST:
                product.service_duration_minutes = None

            if 'image' in request.FILES:
                product.image = request.FILES['image']

            product.description = description
            product.requires_prescription = requires_prescription
            product.expiry_info = expiry_info
            product.is_available = is_available
            product.save()

            log_audit(
                performed_by=request.user,
                action=AuditLog.Action.PRODUCT_UPDATE,
                target_type='Product',
                target_id=product.id,
                target_identifier=product.name,
                reason=f"Edited details in shop {product.shop.name}"
            )
            messages.success(request, f"'{name}' വിജയകരമായി പുതുക്കി.")
        except Exception as e:
            messages.error(request, f"പുതുക്കുന്നതിൽ പിശക്: {e}")

        return redirect('shop-dashboard')

    # GET request - render modal or edit form in dashboard
    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_product_toggle_stock(request, product_id):
    """
    Toggles product in-stock / out-of-stock.
    Enforces strict ownership: product.shop.owner must equal request.user.
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    product = _get_manageable_product_or_403(request.user, product_id)

    target_state = request.POST.get('is_available')
    if target_state is not None:
        product.is_available = target_state in ['on', 'true', '1', True]
    else:
        product.is_available = not product.is_available

    product.save(update_fields=['is_available'])

    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.PRODUCT_STOCK_TOGGLE,
        target_type='Product',
        target_id=product.id,
        target_identifier=product.name,
        reason=f"Stock toggled to is_available={product.is_available}"
    )

    state = "ലഭ്യമാണ്" if product.is_available else "ലഭ്യമല്ല"
    messages.success(request, f"'{product.name}' ഇപ്പോൾ {state}.")

    referer = request.META.get('HTTP_REFERER')
    if referer and ('/shops/' in referer or '/dashboard/' in referer):
        return redirect(referer)
    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_product_delete(request, product_id):
    """
    Allows shop owner or admin to delete a product or service.
    Safe Deletion:
    - If the product has historical OrderItem or Booking records, soft-delete/archive it (is_available=False)
      to protect historical records and prevent foreign key errors.
    - If no history exists, safely delete the row.
    Enforces strict ownership: product.shop.owner must equal request.user.
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    product = _get_manageable_product_or_403(request.user, product_id)

    name = product.name
    # Check if the product has historical OrderItem or Booking records
    has_order_history = OrderItem.objects.filter(product=product).exists()
    has_booking_history = Booking.objects.filter(service=product).exists()
    if has_order_history or has_booking_history:
        # Soft-delete: mark unavailable and archived to protect historical records
        product.is_available = False
        product.save(update_fields=['is_available'])
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.PRODUCT_DELETE,
            target_type='Product',
            target_id=product.id,
            target_identifier=name,
            reason="Soft-deleted (marked unavailable) because product is linked to orders/bookings"
        )
        messages.success(request, f"'{name}' പഴയ രേഖകളിൽ ഉൾപ്പെട്ടിരിക്കുന്നതിനാൽ കാറ്റലോഗിൽ നിന്ന് ആർക്കൈവ് ചെയ്തു (ലഭ്യമല്ലെന്ന് അടയാളപ്പെടുത്തി).")
    else:
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.PRODUCT_DELETE,
            target_type='Product',
            target_id=product.id,
            target_identifier=name,
            reason="Hard-deleted product"
        )
        product.delete()
        messages.success(request, f"'{name}' വിജയകരമായി നീക്കം ചെയ്തു.")

    referer = request.META.get('HTTP_REFERER')
    if referer and ('/shops/' in referer or '/dashboard/' in referer):
        return redirect(referer)
    return redirect('shop-dashboard')


# ==============================================================================
# APPOINTMENT & BOOKING ACTIONS (FOR PARLOURS, SALONS & SERVICES)
# ==============================================================================

@login_required(login_url='web-login')
def web_booking_create(request, shop_id):
    """
    Allows a customer to request an appointment at a parlour, salon, or service shop.
    """
    if request.method != 'POST':
        return redirect('shop-detail', shop_id=shop_id)

    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.warning(request, "അഡ്മിൻമാർക്ക് അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യാൻ അനുവാദമില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    shop = get_object_or_404(Shop, id=shop_id, is_verified=True)

    if request.user.is_authenticated and shop.owner_id == request.user.id:
        messages.error(request, "നിങ്ങളുടെ സ്വന്തം സ്ഥാപനത്തിൽ അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യാൻ കഴിയില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    service_id = request.POST.get('service_id')
    service = None
    if service_id and service_id.isdigit():
        service = shop.products.filter(id=int(service_id)).first()

    booking_date_str = request.POST.get('booking_date', '').strip()
    time_slot = request.POST.get('time_slot', '').strip()
    customer_phone = request.POST.get('customer_phone', '').strip() or request.user.phone_number
    number_of_people = request.POST.get('number_of_people', '1').strip()
    special_notes = request.POST.get('special_notes', '').strip()

    if not booking_date_str or not time_slot:
        messages.error(request, "ദയവായി തീയതിയും സമയ സ്ലോട്ടും നൽകുക.")
        return redirect('shop-detail', shop_id=shop_id)

    try:
        booking_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "തീയതി ശരിയായ ഫോർമാറ്റിൽ നൽകുക (YYYY-MM-DD).")
        return redirect('shop-detail', shop_id=shop_id)

    try:
        people_count = max(1, int(number_of_people))
    except ValueError:
        people_count = 1

    booking = Booking.objects.create(
        customer=request.user,
        shop=shop,
        service=service,
        booking_date=booking_date,
        time_slot=time_slot,
        number_of_people=people_count,
        customer_phone=customer_phone,
        special_notes=special_notes,
        status=Booking.Status.PENDING
    )

    notify_booking_requested(booking)
    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.BOOKING_STATUS_UPDATE,
        target_type='Booking',
        target_id=booking.id,
        target_identifier=f"Booking #{booking.id}",
        reason=f"Appointment requested for {formatted_date} ({time_slot})"
    )

    formatted_date = booking_date.strftime('%d-%m-%Y')
    messages.success(
        request,
        f"{shop.name}-ലേക്ക് നിങ്ങളുടെ അപ്പോയിന്റ്മെന്റ് അഭ്യർത്ഥന ({formatted_date} {time_slot}) ലഭിച്ചു! സ്ഥാപനം ഉടൻ സ്ഥിരീകരിക്കും."
    )
    return redirect('shop-detail', shop_id=shop_id)


@login_required(login_url='web-login')
def web_booking_update_status(request, booking_id):
    """
    Allows shop owner to update booking status (confirm, complete, cancel).
    Strict ownership check: booking.shop.owner must equal request.user.
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    booking = get_object_or_404(Booking.objects.select_related('shop', 'shop__owner'), id=booking_id)

    if booking.shop.owner_id != request.user.id and not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        raise PermissionDenied("മറ്റൊരു സ്ഥാപനത്തിന്റെ അപ്പോയിന്റ്മെന്റുകൾ മാറ്റാൻ നിങ്ങൾക്ക് അധികാരമില്ല.")

    new_status = request.POST.get('status', '').strip()
    if new_status in Booking.Status.values:
        booking.status = new_status
        booking.save(update_fields=['status'])
        notify_booking_status_changed(booking, performed_by=request.user)
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.BOOKING_STATUS_UPDATE,
            target_type='Booking',
            target_id=booking.id,
            target_identifier=f"Booking #{booking.id}",
            reason=f"Shop owner updated status to {new_status}"
        )
        messages.success(request, f"അപ്പോയിന്റ്മെന്റ് #{booking.id} സ്റ്റാറ്റസ് '{booking.get_status_display()}' ആയി മാറ്റി.")
    else:
        messages.error(request, "അസാധുവായ സ്റ്റാറ്റസ്.")

    referer = request.META.get('HTTP_REFERER')
    if referer and '/dashboard/' in referer:
        return redirect(referer)
    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_booking_cancel(request, booking_id):
    """
    Allows customer who made the booking (or shop owner) to cancel booking.
    Business Rule:
    - If customer cancels: only allowed while status is 'PENDING'.
      Once the shop owner confirms/approves ('CONFIRMED' or 'COMPLETED'), the customer cannot cancel.
    - If shop owner cancels: allowed anytime prior to completion.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    booking = get_object_or_404(Booking.objects.select_related('shop', 'customer'), id=booking_id)

    is_customer = (booking.customer_id == request.user.id)
    is_owner = (booking.shop.owner_id == request.user.id)
    is_admin = (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN)

    if not (is_customer or is_owner or is_admin):
        raise PermissionDenied("ഈ അപ്പോയിന്റ്മെന്റ് റദ്ദാക്കാൻ നിങ്ങൾക്ക് അനുവാദമില്ല.")

    # Guard: If customer tries to cancel after shop confirmed/approved
    if is_customer and not is_owner and not is_admin:
        if booking.status != Booking.Status.PENDING:
            messages.error(request, "സ്ഥാപനം സ്ഥിരീകരിച്ച (Approved) അപ്പോയിന്റ്മെന്റുകൾ നേരിട്ട് ക്യാൻസൽ ചെയ്യാൻ കഴിയില്ല. ദയവായി കടയുമായി ഫോണിൽ ബന്ധപ്പെടുക.")
            referer = request.META.get('HTTP_REFERER')
            if referer and '/dashboard/' in referer:
                return redirect(referer)
            return redirect('user-dashboard')

    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=['status'])
    notify_booking_status_changed(booking, performed_by=request.user)
    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.BOOKING_CANCEL,
        target_type='Booking',
        target_id=booking.id,
        target_identifier=f"Booking #{booking.id}",
        reason=f"Appointment cancelled by {'owner' if is_owner else 'customer'}"
    )
    messages.success(request, f"അപ്പോയിന്റ്മെന്റ് #{booking.id} റദ്ദാക്കി.")

    referer = request.META.get('HTTP_REFERER')
    if referer and '/dashboard/' in referer:
        return redirect(referer)
    return redirect('shop-dashboard' if is_owner else 'user-dashboard')


@login_required(login_url='web-login')
def web_submit_review(request, shop_id):
    """
    Submits a Category-Based verified review for a shop.
    Security & Validation:
    - User must be authenticated citizen/buyer.
    - Shop owners cannot review their own shop.
    - User must have a completed order or completed booking with this shop.
    - Prevents duplicate reviews.
    - Overall rating strictly 1 to 5.
    - Criterion ratings strictly 1 to 5 with optional written feedback.
    - Atomically creates Review and ReviewCriterionRating records.
    """
    if request.method != 'POST':
        return redirect('shop-detail', shop_id=shop_id)

    shop = get_object_or_404(Shop, id=shop_id)
    user = request.user

    # Rule: Shop owners cannot review their own shop
    if shop.owner_id == user.id:
        messages.error(request, "കടയുടമകൾക്ക് സ്വന്തം കടയ്ക്ക് റേറ്റിംഗ് നൽകാൻ അനുവാദമില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    # Rule: Duplicate review prevention
    if Review.objects.filter(shop=shop, user=user).exists():
        messages.warning(request, "നിങ്ങൾ ഇതിനകം ഈ കടയ്ക്ക് റേറ്റിംഗ് നൽകിയിട്ടുണ്ട്. നന്ദി!")
        return redirect('shop-detail', shop_id=shop_id)

    order_id = request.POST.get('order_id')
    booking_id = request.POST.get('booking_id')
    verified_order = None
    verified_booking = None

    # Validate booking-based review
    if booking_id and booking_id.isdigit():
        try:
            booking = Booking.objects.get(id=int(booking_id), customer=user, shop=shop)
            if booking.status != Booking.Status.COMPLETED:
                messages.error(request, f"പൂർത്തിയായ ബുക്കിംഗുകൾക്ക് മാത്രമേ റേറ്റിംഗ് നൽകാൻ സാധിക്കൂ (Status: {booking.get_status_display()}).")
                return redirect('user-dashboard')
            if Review.objects.filter(booking=booking).exists():
                messages.warning(request, "ഈ ബുക്കിംഗിന് ഇതിനകം റിവ്യൂ നൽകിയിട്ടുണ്ട്.")
                return redirect('user-dashboard')
            verified_booking = booking
        except Booking.DoesNotExist:
            messages.error(request, "അസാധുവായ ബുക്കിംഗ് വിവരങ്ങൾ.")
            return redirect('user-dashboard')

    # Validate order-based review
    elif order_id and order_id.isdigit():
        try:
            order = Order.objects.get(id=int(order_id), customer=user, shop=shop)
            if order.status != Order.Status.COMPLETED:
                messages.error(request, f"പൂർത്തിയായ ഓർഡറുകൾക്ക് മാത്രമേ റേറ്റിംഗ് നൽകാൻ സാധിക്കൂ (Status: {order.get_status_display()}).")
                return redirect('user-dashboard')
            if Review.objects.filter(order=order).exists():
                messages.warning(request, "ഈ ഓർഡറിന് ഇതിനകം റിവ്യൂ നൽകിയിട്ടുണ്ട്.")
                return redirect('user-dashboard')
            verified_order = order
        except Order.DoesNotExist:
            messages.error(request, "അസാധുവായ ഓർഡർ വിവരങ്ങൾ.")
            return redirect('user-dashboard')

    else:
        # Fallback: check if customer has ANY completed order or booking for this shop
        verified_order = Order.objects.filter(
            customer=user, shop=shop, status=Order.Status.COMPLETED
        ).exclude(reviews__isnull=False).first()

        if not verified_order:
            verified_booking = Booking.objects.filter(
                customer=user, shop=shop, status=Booking.Status.COMPLETED
            ).exclude(reviews__isnull=False).first()

        if not verified_order and not verified_booking:
            messages.error(request, "ഈ കടയ്ക്ക് റിവ്യൂ നൽകാൻ പൂർത്തിയായ ഓർഡറോ ബുക്കിംഗോ ആവശ്യമാണ്.")
            return redirect('shop-detail', shop_id=shop_id)

    # Validate overall star rating
    try:
        rating_val = int(request.POST.get('rating', 5))
        if not (1 <= rating_val <= 5):
            raise ValueError()
    except (ValueError, TypeError):
        messages.error(request, "സാധുവായ ഓവറോൾ റേറ്റിംഗ് (1-5 നക്ഷത്രങ്ങൾ) നൽകുക.")
        return redirect('shop-detail', shop_id=shop_id)

    comment = request.POST.get('comment', '').strip()

    # Save Review and Category-Specific Criteria Ratings atomically
    with transaction.atomic():
        review = Review.objects.create(
            shop=shop,
            user=user,
            order=verified_order,
            booking=verified_booking,
            rating=rating_val,
            comment=comment,
            is_verified_buyer=True,
        )

        # Process each category criterion
        criteria_list = shop.get_rating_criteria()
        for crit in criteria_list:
            slug = crit['slug']
            score_str = request.POST.get(f'criteria_{slug}')
            crit_feedback = request.POST.get(f'feedback_{slug}', '').strip()

            crit_score = rating_val  # default to overall rating if not specified
            if score_str:
                try:
                    parsed_score = int(score_str)
                    if 1 <= parsed_score <= 5:
                        crit_score = parsed_score
                except (ValueError, TypeError):
                    pass

            criterion_obj = None
            if crit.get('id'):
                criterion_obj = RatingCriterion.objects.filter(id=crit['id']).first()

            ReviewCriterionRating.objects.create(
                review=review,
                criterion=criterion_obj,
                criterion_name=crit['name'],
                criterion_name_ml=crit.get('name_ml', crit['name']),
                criterion_slug=slug,
                rating=crit_score,
                feedback=crit_feedback
            )

    messages.success(request, f"'{shop.name}'-ന് നിങ്ങളുടെ വിലയേറിയ റേറ്റിംഗും അഭിപ്രായവും വിജയകരമായി രേഖപ്പെടുത്തി! നന്ദി.")

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    if verified_order:
        return redirect('order-detail', order_id=verified_order.id)
    return redirect('shop-detail', shop_id=shop_id)


@login_required(login_url='web-login')
def web_order_create(request, shop_id):
    """
    Places an order from the shop detail page.
    """
    if request.method != 'POST':
        return redirect('shop-detail', shop_id=shop_id)

    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.warning(request, "അഡ്മിൻമാർക്ക് ഓർഡറുകൾ നൽകാൻ അനുവാദമില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    shop = get_object_or_404(Shop, id=shop_id, is_verified=True)

    if shop.owner_id == request.user.id:
        messages.error(request, "നിങ്ങളുടെ സ്വന്തം കടയിൽ നിന്ന് സാധനങ്ങൾ ഓർഡർ ചെയ്യാൻ കഴിയില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    if not shop.is_open:
        messages.error(request, "ക്ഷമിക്കണം, ഈ കട ഇപ്പോൾ അടച്ചിരിക്കുകയാണ്. ഓർഡറുകൾ സ്വീകരിക്കാൻ കഴിയില്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    delivery_type = request.POST.get('delivery_type', Order.DeliveryType.STORE_PICKUP)
    delivery_address = request.POST.get('delivery_address', '').strip()
    customer_phone = request.POST.get('customer_phone', '').strip() or request.user.phone_number
    notes = request.POST.get('notes', '').strip()

    product = get_object_or_404(Product, id=product_id, shop=shop)
    if not product.is_available:
        messages.error(request, f"'{product.name}' നിലവിൽ ലഭ്യമല്ല.")
        return redirect('shop-detail', shop_id=shop_id)

    total_amount = product.price * quantity

    try:
        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                shop=shop,
                status=Order.Status.PENDING,
                delivery_type=delivery_type,
                delivery_address=delivery_address,
                customer_phone=customer_phone,
                notes=notes,
                total_amount=total_amount
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=quantity,
                subtotal=total_amount
            )
            notify_order_created(order)
            log_audit(
                performed_by=request.user,
                action=AuditLog.Action.ORDER_STATUS_UPDATE,
                target_type='Order',
                target_id=order.id,
                target_identifier=f"Order #{order.id}",
                reason=f"Order placed with {shop.name} for ₹{total_amount}"
            )
            messages.success(request, f"നിങ്ങളുടെ ഓർഡർ (#{order.id}) വിജയകരമായി അയച്ചു! കടക്കാരൻ സ്ഥിരീകരിക്കുമ്പോൾ അറിയിക്കും.")
            return redirect('user-dashboard')
    except Exception as e:
        messages.error(request, f"ഓർഡർ സമർപ്പിക്കുന്നതിൽ പിശക്: {e}")
        return redirect('shop-detail', shop_id=shop_id)


@login_required(login_url='web-login')
def web_order_update_status(request, order_id):
    """
    Shop owner updates order status (accepted, preparing, ready, completed, cancelled).
    """
    if request.method != 'POST':
        return redirect('shop-dashboard')

    order = get_object_or_404(Order, id=order_id)
    if order.shop.owner != request.user and not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
        raise PermissionDenied("നിങ്ങൾക്ക് ഈ ഓർഡർ നിയന്ത്രിക്കാൻ അധികാരമില്ല.")

    new_status = request.POST.get('status')
    if new_status in Order.Status.values:
        order.status = new_status
        order.save(update_fields=['status'])
        notify_order_status_changed(order)
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.ORDER_STATUS_UPDATE,
            target_type='Order',
            target_id=order.id,
            target_identifier=f"Order #{order.id}",
            reason=f"Shop owner updated status to {new_status}"
        )
        messages.success(request, f"ഓർഡർ #{order.id} സ്റ്റാറ്റസ് '{order.get_status_display()}' എന്ന് മാറ്റി.")
    else:
        messages.error(request, "തെറ്റായ സ്റ്റാറ്റസ്.")

    return redirect('shop-dashboard')


@login_required(login_url='web-login')
def web_complaint_create(request):
    """
    Citizens submit grievances, public complaints, or development suggestions.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    title = request.POST.get('title', '').strip()
    category = request.POST.get('category', Complaint.Category.OTHER)
    description = request.POST.get('description', '').strip()
    ward_number = request.POST.get('ward_number', '').strip()
    location_details = request.POST.get('location_details', '').strip()
    is_anonymous = request.POST.get('is_anonymous') in ['1', 'on', 'true']

    if not title or not description:
        messages.error(request, "പരാതിയുടെ തലക്കെട്ടും വിവരണവും നിർബന്ധമാണ്.")
        return redirect('user-dashboard')

    parsed_ward = int(ward_number) if ward_number and ward_number.isdigit() else (request.user.ward_number or 1)

    try:
        Complaint.objects.create(
            citizen=request.user,
            area=request.user.area,
            title=title,
            category=category,
            description=description,
            ward_number=parsed_ward,
            location_details=location_details,
            is_anonymous=is_anonymous,
            status=Complaint.Status.SUBMITTED
        )
        messages.success(request, "നിങ്ങളുടെ പരാതി വിജയകരമായി സമർപ്പിച്ചു. അഡ്മിൻ പരിശോധിച്ച ശേഷം നടപടി സ്വീകരിക്കും.")
    except Exception as e:
        messages.error(request, f"പരാതി സമർപ്പിക്കുന്നതിൽ പിശക്: {e}")

    return redirect('user-dashboard')


@login_required(login_url='web-login')
def web_complaint_delete(request, complaint_id):
    """
    Citizen deletes their own complaint, or Super Admin/Ward Admin deletes a complaint.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    complaint = get_object_or_404(Complaint, id=complaint_id)
    if complaint.citizen != request.user and not request.user.is_staff and request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.error(request, "ഈ പരാതി നീക്കം ചെയ്യാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
        return redirect('user-dashboard')

    title = complaint.title
    complaint.delete()
    messages.success(request, f"'{title}' എന്ന പരാതി വിജയകരമായി നീക്കം ചെയ്തു.")
    referer = request.META.get('HTTP_REFERER')
    if referer and '/dashboard/' in referer:
        return redirect(referer)
    if request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN:
        return redirect('admin-dashboard')
    return redirect('user-dashboard')


@login_required(login_url='web-login')
def web_order_cancel(request, order_id):
    """
    Customer cancels their pending order.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    order = get_object_or_404(Order, id=order_id)
    if order.customer != request.user and order.shop.owner != request.user and not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
        messages.error(request, "ഈ ഓർഡർ മാറ്റാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
        return redirect('user-dashboard')

    if order.customer == request.user and order.status != Order.Status.PENDING:
        messages.error(request, "കടയുടമ സ്വീകരിച്ച ഓർഡറുകൾ ക്യാൻസൽ ചെയ്യാൻ കഴിയില്ല.")
        return redirect('user-dashboard')

    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status'])
    notify_order_status_changed(order)
    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.ORDER_CANCEL,
        target_type='Order',
        target_id=order.id,
        target_identifier=f"Order #{order.id}",
        reason=f"Order cancelled by {'owner' if order.shop.owner == request.user else 'customer'}"
    )
    messages.success(request, f"ഓർഡർ #{order.id} വിജയകരമായി ക്യാൻസൽ ചെയ്തു.")
    return redirect('user-dashboard')


# ==============================================================================
# ADMIN QUICK ACTION ENDPOINTS (Verified Super Admin Only)
# ==============================================================================

@login_required(login_url='web-login')
def web_admin_verify_shop(request, shop_id):
    """
    Super Admin marks a pending shop as verified.
    """
    if request.method != 'POST':
        return redirect('admin-dashboard')

    if not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അധികാരമില്ല.")
        return redirect('home')

    shop = get_object_or_404(Shop, id=shop_id)
    shop.is_verified = True
    shop.save(update_fields=['is_verified'])
    messages.success(request, f"കട '{shop.name}' വിജയകരമായി പരിശോധിച്ചു അപ്രൂവ് ചെയ്തു!")
    return redirect('admin-dashboard')


@login_required(login_url='web-login')
def web_admin_notice_create(request):
    """
    Super Admin broadcasts an emergency alert or community announcement.
    """
    if request.method != 'POST':
        return redirect('admin-dashboard')

    if not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അധികാരമില്ല.")
        return redirect('home')

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    category = request.POST.get('category', EventNotice.Category.GENERAL)
    is_emergency = request.POST.get('is_emergency') in ['1', 'on', 'true']
    venue = request.POST.get('venue', '').strip()

    if not title or not description:
        messages.error(request, "തലക്കെട്ടും വിവരണവും നൽകണം.")
        return redirect('admin-dashboard')

    try:
        EventNotice.objects.create(
            author=request.user,
            area=request.user.area,
            title=title,
            description=description,
            category=category,
            is_emergency=is_emergency,
            venue=venue
        )
        alert_type = "അടിയന്തര മുന്നറിയിപ്പ്" if is_emergency else "അറിയിപ്പ്"
        messages.success(request, f"പുതിയ {alert_type} വിജയകരമായി പ്രസിദ്ധീകരിച്ചു!")
    except Exception as e:
        messages.error(request, f"അറിയിപ്പ് പ്രസിദ്ധീകരിക്കുന്നതിൽ പിശക്: {e}")

    return redirect('admin-dashboard')


@login_required(login_url='web-login')
def web_admin_complaint_resolve(request, complaint_id):
    """
    Super Admin updates complaint status and writes official remarks.
    """
    if request.method != 'POST':
        return redirect('admin-dashboard')

    if not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അധികാരമില്ല.")
        return redirect('home')

    complaint = get_object_or_404(Complaint, id=complaint_id)
    new_status = request.POST.get('status')
    remarks = request.POST.get('remarks', '').strip()

    if new_status in Complaint.Status.values:
        complaint.status = new_status
    if remarks:
        complaint.admin_remarks = remarks
    complaint.save()

    if complaint.status == Complaint.Status.RESOLVED:
        notify_complaint_status(complaint, admin_user=request.user)

    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.COMPLAINT_RESOLVE,
        target_type='Complaint',
        target_id=complaint.id,
        target_identifier=complaint.title,
        reason=f"Status set to {complaint.status}. Remarks: {remarks}"
    )

    messages.success(request, f"പരാതി #{complaint.id} സ്റ്റാറ്റസ് '{complaint.get_status_display()}' എന്ന് രേഖപ്പെടുത്തി.")
    return redirect('admin-dashboard')


@login_required(login_url='web-login')
def web_notice_delete(request, notice_id):
    """
    Author or Super Admin deletes an announcement/notice.
    """
    if request.method != 'POST':
        return redirect('admin-dashboard')

    notice = get_object_or_404(EventNotice, id=notice_id)
    if notice.author != request.user and not request.user.is_staff and request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.error(request, "ഈ അറിയിപ്പ് നീക്കം ചെയ്യാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
        return redirect('admin-dashboard')

    title = notice.title
    notice.delete()
    messages.success(request, f"'{title}' എന്ന അറിയിപ്പ് വിജയകരമായി നീക്കം ചെയ്തു.")
    return redirect('admin-dashboard')


# ==============================================================================
# AUTHENTICATION HANDLERS
# ==============================================================================

def web_user_register_view(request):
    """
    Handles Citizen / Resident registration directly from the Web Home Page.
    """
    if request.method != 'POST':
        return redirect('home')

    full_name = request.POST.get('full_name', '').strip()
    phone_number = request.POST.get('phone_number', '').strip().replace(' ', '')
    password = request.POST.get('password', '').strip()
    ward_number = request.POST.get('ward_number', '').strip()
    address = request.POST.get('address', '').strip()
    area_id = request.POST.get('area_id', '').strip()
    state = request.POST.get('state', '').strip() or 'Kerala'
    district = request.POST.get('district', '').strip()
    panchayat_name = request.POST.get('panchayat_name', '').strip()
    custom_panchayat = request.POST.get('custom_panchayat', '').strip()
    if custom_panchayat:
        panchayat_name = custom_panchayat

    if not full_name or not phone_number or not password:
        messages.error(request, "പൂർണ്ണ നാമം, ഫോൺ നമ്പർ, പാസ്‌വേഡ് എന്നിവ നിർബന്ധമാണ്.")
        return redirect('home')

    if len(password) < 6:
        messages.error(request, "പാസ്‌വേഡിൽ കുറഞ്ഞത് 6 അക്ഷരങ്ങൾ ഉണ്ടായിരിക്കണം.")
        return redirect('home')

    if User.objects.filter(phone_number=phone_number).exists():
        messages.error(request, "ഈ ഫോൺ നമ്പറിൽ ഇതിനകം അക്കൗണ്ട് ഉണ്ട്. ലോഗിൻ ചെയ്യുക.")
        return redirect('home')

    parsed_ward = int(ward_number) if ward_number and ward_number.isdigit() else None
    parsed_area = None
    if area_id and area_id.isdigit():
        parsed_area = Area.objects.filter(id=area_id).first()
    if not parsed_area and panchayat_name:
        parsed_area = Area.objects.filter(name__iexact=panchayat_name).first()
        if not parsed_area:
            parsed_area = Area.objects.create(
                name=panchayat_name,
                district=district or 'തിരുവനന്തപുരം',
                state=state or 'കേരളം',
                is_active=True
            )

    try:
        user = User.objects.create_user(
            phone_number=phone_number,
            password=password,
            full_name=full_name,
            role=User.Role.CITIZEN,
            ward_number=parsed_ward,
            address=address,
            area=parsed_area
        )
        login(request, user)
        messages.success(request, f"സ്വാഗതം {user.full_name}! നിങ്ങളുടെ അക്കൗണ്ട് വിജയകരമായി സൃഷ്ടിച്ചു.")
        return redirect('user-dashboard')
    except Exception as e:
        messages.error(request, f"രജിസ്ട്രേഷൻ പരാജയപ്പെട്ടു: {e}")

    return redirect('home')


def web_shop_register_view(request):
    """
    Handles Shop Registration directly from the Web Home Page.
    Creates or links the User account and creates the Shop in one atomic step.
    """
    if request.method != 'POST':
        return redirect('home')

    owner_name = request.POST.get('owner_name', '').strip()
    owner_phone = request.POST.get('owner_phone', '').strip().replace(' ', '')
    owner_password = request.POST.get('owner_password', '').strip()

    shop_name = request.POST.get('shop_name', '').strip()
    category_id = request.POST.get('category_id', '').strip()
    contact_phone = request.POST.get('contact_phone', '').strip().replace(' ', '') or owner_phone
    whatsapp_number = request.POST.get('whatsapp_number', '').strip().replace(' ', '')
    ward_number = request.POST.get('ward_number', '').strip()
    address = request.POST.get('address', '').strip()
    delivery_available = request.POST.get('delivery_available') in ['on', 'true', '1']
    description = request.POST.get('description', '').strip()
    area_id = request.POST.get('area_id', '').strip()
    state = request.POST.get('state', '').strip() or 'Kerala'
    district = request.POST.get('district', '').strip()
    panchayat_name = request.POST.get('panchayat_name', '').strip()
    custom_panchayat = request.POST.get('custom_panchayat', '').strip()
    if custom_panchayat:
        panchayat_name = custom_panchayat

    raw_lat = request.POST.get('latitude', '').strip()
    raw_lng = request.POST.get('longitude', '').strip()
    latitude = None
    longitude = None
    if raw_lat and raw_lng and is_valid_coord(raw_lat, raw_lng):
        latitude = Decimal(raw_lat)
        longitude = Decimal(raw_lng)

    # If already logged in, use current user
    if request.user.is_authenticated:
        user = request.user
        if user.role != User.Role.SHOP_OWNER and user.role != User.Role.SUPER_ADMIN:
            user.role = User.Role.SHOP_OWNER
            user.save(update_fields=['role'])
    else:
        if not owner_name or not owner_phone or not owner_password:
            messages.error(request, "ഉടമസ്ഥന്റെ പേര്, ഫോൺ നമ്പർ, പാസ്‌വേഡ് എന്നിവ നിർബന്ധമാണ്.")
            return redirect('home')

        if len(owner_password) < 6:
            messages.error(request, "പാസ്‌വേഡിൽ കുറഞ്ഞത് 6 അക്ഷരങ്ങൾ ഉണ്ടായിരിക്കണം.")
            return redirect('home')

    if not shop_name or not ward_number or not address:
        messages.error(request, "കടയുടെ പേര്, വാർഡ് നമ്പർ, വിലാസം എന്നിവ നിർബന്ധമാണ്.")
        return redirect('home')

    parsed_ward = int(ward_number) if ward_number.isdigit() else 1
    category = ShopCategory.objects.filter(id=category_id).first() if category_id and category_id.isdigit() else None

    area = None
    if area_id and area_id.isdigit():
        area = Area.objects.filter(id=area_id).first()
    if not area and panchayat_name:
        area = Area.objects.filter(name__iexact=panchayat_name).first()
        if not area:
            area = Area.objects.create(
                name=panchayat_name,
                district=district or 'തിരുവനന്തപുരം',
                state=state or 'കേരളം',
                is_active=True
            )

    try:
        with transaction.atomic():
            if not request.user.is_authenticated:
                user = User.objects.filter(phone_number=owner_phone).first()
                if user:
                    if not user.check_password(owner_password):
                        messages.error(request, "ഈ ഫോൺ നമ്പറിൽ ഇതിനകം അക്കൗണ്ട് ഉണ്ട്. നൽകിയ പാസ്‌വേഡ് ശരിയല്ല.")
                        return redirect('home')
                    if user.role != User.Role.SHOP_OWNER and user.role != User.Role.SUPER_ADMIN:
                        user.role = User.Role.SHOP_OWNER
                        user.save(update_fields=['role'])
                else:
                    user = User.objects.create_user(
                        phone_number=owner_phone,
                        password=owner_password,
                        full_name=owner_name,
                        role=User.Role.SHOP_OWNER,
                        ward_number=parsed_ward,
                        area=area,
                        address=address
                    )
                login(request, user)

            shop = Shop.objects.create(
                owner=user,
                name=shop_name,
                category=category,
                area=area,
                contact_phone=contact_phone,
                whatsapp_number=whatsapp_number,
                address=address,
                ward_number=parsed_ward,
                delivery_available=delivery_available,
                description=description,
                latitude=latitude,
                longitude=longitude,
                is_open=True,
                is_verified=False
            )

            messages.success(
                request,
                f"നിങ്ങളുടെ കട '{shop.name}' വിജയകരമായി രജിസ്റ്റർ ചെയ്തു! അഡ്മിൻ പരിശോധനയ്ക്ക് ശേഷം ലിസ്റ്റ് ചെയ്യപ്പെടും."
            )
            return redirect('shop-dashboard')
    except Exception as e:
        messages.error(request, f"കട രജിസ്ട്രേഷൻ പരാജയപ്പെട്ടു: {e}")

    return redirect('home')


@ensure_csrf_cookie
def web_login_view(request):
    """
    Handles User / Shop Owner login directly from the Web Home Page.
    """
    if request.method != 'POST':
        return redirect('home')

    phone_number = request.POST.get('phone_number', '').strip().replace(' ', '')
    password = request.POST.get('password', '').strip()

    if not phone_number or not password:
        messages.error(request, "ഫോൺ നമ്പറും പാസ്‌വേഡും നൽകുക.")
        return redirect('home')

    user = authenticate(request, username=phone_number, password=password)
    if user is not None:
        if user.is_blocked:
            reason = user.block_reason or "കമ്മ്യൂണിറ്റി മാർഗ്ഗനിർദ്ദേശങ്ങളുടെ ലംഘനം."
            messages.error(request, f"നിങ്ങളുടെ അക്കൗണ്ട് ബ്ലോക്ക് ചെയ്തിരിക്കുകയാണ്: {reason}")
            return redirect('home')
        if not user.is_active:
            messages.error(request, "ഈ അക്കൗണ്ട് നിർജ്ജീവമാണ്. അഡ്മിനെ ബന്ധപ്പെടുക.")
            return redirect('home')

        login(request, user)
        messages.success(request, f"സ്വാഗതം {user.full_name}! നിങ്ങൾ ലോഗിൻ ചെയ്തു.")

        # Smart redirection based on role
        if user.is_staff or user.role == User.Role.SUPER_ADMIN:
            return redirect('admin-dashboard')
        elif user.role == User.Role.SHOP_OWNER:
            return redirect('shop-dashboard')
        else:
            return redirect('user-dashboard')
    else:
        messages.error(request, "തെറ്റായ ഫോൺ നമ്പറോ പാസ്‌വേഡോ ആണ് നൽകിയത്.")

    return redirect('home')


def web_logout_view(request):
    """
    Logs out the user and redirects to the Web Home Page.
    """
    logout(request)
    messages.info(request, "വിജയകരമായി ലോഗൗട്ട് ചെയ്തു.")
    return redirect('home')


def csrf_failure_view(request, reason=""):
    """
    Gracefully handles CSRF verification mismatches/expiry:
    Sets an informative flash message and safely redirects the user back to the home page with a fresh token.
    """
    messages.warning(request, "സുരക്ഷാ ടോക്കൺ കാലഹരണപ്പെട്ടു. പേജ് വീണ്ടും പുതുക്കി ലോഗിൻ ചെയ്യുക.")
    return redirect('home')


# ==============================================================================
# SHOPPING CART & MULTI-SHOP CHECKOUT VIEWS
# ==============================================================================

def web_cart_view(request):
    """
    Renders customer shopping cart with shop-wise grouped cards, subtotals,
    stock validation warnings, and prescription alerts.
    """
    if not request.user.is_authenticated:
        messages.info(request, "ഷോപ്പിംഗ് കാർട്ട് പരിശോധിക്കാൻ ദയവായി ലോഗിൻ ചെയ്യുക.")
        return redirect('home')

    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.info(request, "അഡ്മിൻമാർക്ക് ഷോപ്പിംഗ് കാർട്ട് സൗകര്യം ലഭ്യമല്ല.")
        return redirect('admin-dashboard')

    try:
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        grouped_shops = cart.get_items_grouped_by_shop()
    except Exception as e:
        if 'no such column' in str(e) or 'no such table' in str(e):
            _safe_ensure_migrations()
            cart, _ = Cart.objects.get_or_create(customer=request.user)
            grouped_shops = cart.get_items_grouped_by_shop()
        else:
            raise

    has_prescription = any(g['has_prescription'] for g in grouped_shops)
    has_closed_shop = any(not g['is_open'] for g in grouped_shops)

    context = {
        'cart': cart,
        'grouped_items': grouped_shops,
        'grouped_shops': grouped_shops,
        'total_items': cart.total_items,
        'total_amount': cart.total_amount,
        'has_prescription': has_prescription,
        'has_closed_shop': has_closed_shop,
    }
    return render(request, 'orders/cart.html', context)


def web_cart_add(request, product_id):
    """
    Adds a product to the user's shopping cart with stock & shop verification.
    """
    if not request.user.is_authenticated:
        messages.info(request, "സാധനങ്ങൾ കാർട്ടിലേക്ക് ചേർക്കാൻ ദയവായി ലോഗിൻ ചെയ്യുക.")
        return redirect(request.META.get('HTTP_REFERER') or 'home')

    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.warning(request, "അഡ്മിൻമാർക്ക് സാധനങ്ങൾ കാർട്ടിലേക്ക് ചേർക്കാൻ അനുവാദമില്ല.")
        return redirect(request.META.get('HTTP_REFERER') or 'shop-list')

    if request.method != 'POST':
        return redirect('shop-list')

    product = get_object_or_404(Product.objects.select_related('shop'), id=product_id)

    if product.shop.owner_id == request.user.id:
        messages.error(request, "നിങ്ങളുടെ സ്വന്തം കടയിലെ സാധനങ്ങൾ കാർട്ടിലേക്ക് ചേർക്കാൻ കഴിയില്ല.")
        return redirect(request.META.get('HTTP_REFERER') or 'shop-detail', shop_id=product.shop.id)

    if not product.is_available:
        messages.error(request, f"'{product.name}' നിലവിൽ ലഭ്യമല്ല (Out of stock).")
        return redirect(request.META.get('HTTP_REFERER') or 'shop-list')

    if not product.shop.is_open:
        messages.error(request, f"'{product.shop.name}' ഇപ്പോൾ അടച്ചിരിക്കുകയാണ്. സാധനങ്ങൾ കാർട്ടിലേക്ക് ചേർക്കാൻ കഴിയില്ല.")
        return redirect(request.META.get('HTTP_REFERER') or 'shop-list')

    try:
        qty = int(request.POST.get('quantity', 1))
        if qty < 1:
            qty = 1
    except ValueError:
        qty = 1

    try:
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': qty}
        )
    except Exception as e:
        if 'no such column' in str(e) or 'no such table' in str(e):
            _safe_ensure_migrations()
            cart, _ = Cart.objects.get_or_create(customer=request.user)
            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': qty}
            )
        else:
            raise

    if not created:
        item.quantity += qty
        item.save(update_fields=['quantity', 'updated_at'])

    messages.success(request, f"'{product.name}' ({qty} {product.unit}) കാർട്ടിലേക്ക് ചേർത്തു.")

    referer = request.META.get('HTTP_REFERER')
    if referer and ('/shops/' in referer or '/cart/' in referer):
        return redirect(referer)
    return redirect('cart-view')


@login_required(login_url='web-login')
def web_cart_update_qty(request, item_id):
    """
    Increments, decrements, or sets quantity of a cart item.
    """
    if request.method != 'POST':
        return redirect('cart-view')

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    item = get_object_or_404(CartItem.objects.select_related('product'), id=item_id, cart=cart)

    action = request.POST.get('action')
    if action in ['increment', 'increase', '+']:
        item.quantity += 1
        item.save(update_fields=['quantity', 'updated_at'])
    elif action in ['decrement', 'decrease', '-']:
        if item.quantity > 1:
            item.quantity -= 1
            item.save(update_fields=['quantity', 'updated_at'])
        else:
            name = item.product.name
            item.delete()
            messages.info(request, f"'{name}' കാർട്ടിൽ നിന്നും ഒഴിവാക്കി.")
            return redirect('cart-view')
    else:
        try:
            qty = int(request.POST.get('quantity', 1))
            if qty <= 0:
                name = item.product.name
                item.delete()
                messages.info(request, f"'{name}' കാർട്ടിൽ നിന്നും ഒഴിവാക്കി.")
                return redirect('cart-view')
            item.quantity = qty
            item.save(update_fields=['quantity', 'updated_at'])
        except ValueError:
            pass

    referer = request.META.get('HTTP_REFERER')
    if referer and '/cart/' in referer:
        return redirect(referer)
    return redirect('cart-view')


@login_required(login_url='web-login')
def web_cart_remove(request, item_id):
    """
    Removes an item completely from the customer's cart.
    """
    if request.method != 'POST':
        return redirect('cart-view')

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    item = get_object_or_404(CartItem.objects.select_related('product'), id=item_id, cart=cart)
    name = item.product.name
    item.delete()
    messages.success(request, f"'{name}' കാർട്ടിൽ നിന്നും നീക്കം ചെയ്തു.")

    referer = request.META.get('HTTP_REFERER')
    if referer and '/cart/' in referer:
        return redirect(referer)
    return redirect('cart-view')


@login_required(login_url='web-login')
def web_cart_clear(request):
    """
    Empties the entire shopping cart.
    """
    if request.method != 'POST':
        return redirect('cart-view')

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    cart.items.all().delete()
    messages.info(request, "ഷോപ്പിംഗ് കാർട്ട് പൂർണ്ണമായും ഒഴിവാക്കി.")
    return redirect('cart-view')


@login_required(login_url='web-login')
def web_checkout_view(request):
    """
    Multi-shop checkout preview: validates item stock, shop open states,
    displays shop-wise summary, and pre-fills user delivery details.
    """
    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.info(request, "അഡ്മിൻമാർക്ക് ചെക്ക്ഔട്ട് സൗകര്യം ലഭ്യമല്ല.")
        return redirect('admin-dashboard')

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    if not cart.items.exists():
        messages.warning(request, "നിങ്ങളുടെ കാർട്ടിൽ സാധനങ്ങൾ ഒന്നും ഇല്ല.")
        return redirect('cart-view')

    grouped_shops = cart.get_items_grouped_by_shop()
    for g in grouped_shops:
        if g['shop'].owner_id == request.user.id:
            messages.error(request, f"നിങ്ങളുടെ സ്വന്തം കടയായ '{g['shop'].name}'-ൽ നിന്നുള്ള സാധനങ്ങൾ കാർട്ടിൽ നിന്ന് ഒഴിവാക്കുക.")
            return redirect('cart-view')
        if not g['is_open']:
            messages.error(request, f"'{g['shop'].name}' ഇപ്പോൾ അടച്ചിരിക്കുകയാണ്. ചെക്ക്ഔട്ട് ചെയ്യുന്നതിന് മുൻപ് ദയവായി ഈ കടയിലെ സാധനങ്ങൾ മാറ്റുക.")
            return redirect('cart-view')
        for item in g['items']:
            if not item.product.is_available:
                messages.error(request, f"'{item.product.name}' നിലവിൽ ലഭ്യമല്ല. ദയവായി ഒഴിവാക്കുക.")
                return redirect('cart-view')

    has_prescription = any(g['has_prescription'] for g in grouped_shops)

    context = {
        'cart': cart,
        'grouped_items': grouped_shops,
        'grouped_shops': grouped_shops,
        'total_items': cart.total_items,
        'total_amount': cart.total_amount,
        'has_prescription': has_prescription,
        'default_address': request.user.address or '',
        'default_phone': request.user.phone_number,
    }
    return render(request, 'orders/checkout.html', context)


@login_required(login_url='web-login')
def web_checkout_place_order(request):
    """
    Atomic multi-shop checkout handler:
    1. Validates cart non-empty and stock availability.
    2. Groups products by shop and creates separate Order instances with a shared checkout_group_id.
    3. Freezes product name and unit price snapshot in OrderItem.
    4. Empties cart only upon successful atomic commit.
    """
    import uuid
    if request.method != 'POST':
        return redirect('checkout-view')

    if request.user.is_staff or request.user.role in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
        messages.warning(request, "അഡ്മിൻമാർക്ക് ഓർഡറുകൾ നൽകാൻ അനുവാദമില്ല.")
        return redirect('admin-dashboard')

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    if not cart.items.exists():
        messages.error(request, "കാർട്ട് കാലിയാണ്. ഓർഡർ നൽകാൻ സാധ്യമല്ല.")
        return redirect('cart-view')

    grouped_shops = cart.get_items_grouped_by_shop()
    for g in grouped_shops:
        if g['shop'].owner_id == request.user.id:
            messages.error(request, f"നിങ്ങളുടെ സ്വന്തം കടയായ '{g['shop'].name}'-ൽ നിന്ന് ഓർഡർ ചെയ്യാൻ സാധ്യമല്ല.")
            return redirect('cart-view')
        if not g['is_open']:
            messages.error(request, f"'{g['shop'].name}' ഇപ്പോൾ അടച്ചിരിക്കുകയാണ്.")
            return redirect('cart-view')
        for item in g['items']:
            if not item.product.is_available:
                messages.error(request, f"'{item.product.name}' നിലവിൽ ലഭ്യമല്ല.")
                return redirect('cart-view')

    delivery_type = request.POST.get('delivery_type', Order.DeliveryType.STORE_PICKUP)
    delivery_address = request.POST.get('delivery_address', '').strip()
    customer_phone = request.POST.get('customer_phone', '').strip() or request.user.phone_number
    notes = request.POST.get('notes', '').strip()

    checkout_group_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
    created_orders = []

    try:
        with transaction.atomic():
            for g in grouped_shops:
                shop = g['shop']
                items = g['items']
                shop_total = Decimal('0.00')

                order = Order.objects.create(
                    customer=request.user,
                    shop=shop,
                    status=Order.Status.PENDING,
                    delivery_type=delivery_type,
                    delivery_address=delivery_address,
                    customer_phone=customer_phone,
                    notes=notes,
                    checkout_group_id=checkout_group_id,
                    total_amount=Decimal('0.00')
                )

                for item in items:
                    price = item.unit_price
                    subtotal = price * item.quantity
                    shop_total += subtotal

                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_name=item.product.name,
                        quantity=item.quantity,
                        unit_price=price,
                        subtotal=subtotal
                    )

                order.total_amount = shop_total
                order.save(update_fields=['total_amount'])
                created_orders.append(order)

            # Successfully created -> clear cart
            cart.items.all().delete()

        order_ids = ", ".join(f"#{o.id}" for o in created_orders)
        messages.success(
            request,
            f"അഭിനന്ദനങ്ങൾ! {len(created_orders)} കടകളിലേക്കായി നിങ്ങളുടെ ഓർഡർ ({order_ids}) വിജയകരമായി നൽകി."
        )
        return redirect('user-dashboard')
    except Exception as e:
        messages.error(request, f"ഓർഡർ സമർപ്പിക്കുന്നതിൽ പിശക് സംഭവിച്ചു: {e}")
        return redirect('checkout-view')


@login_required(login_url='web-login')
def web_order_detail(request, order_id):
    """
    Renders detailed order breakdown and receipt.
    Strictly checks that viewer is the customer, shop owner, or admin.
    """
    order = get_object_or_404(
        Order.objects.select_related('shop', 'shop__owner', 'customer').prefetch_related('items__product'),
        id=order_id
    )

    user = request.user
    is_customer = (order.customer == user)
    is_shop_owner = (order.shop.owner == user)
    is_admin = (user.is_staff or user.role == User.Role.SUPER_ADMIN)

    if not (is_customer or is_shop_owner or is_admin):
        messages.error(request, "ഈ ഓർഡർ കാണാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
        return redirect('user-dashboard')

    sibling_orders = []
    if is_customer and order.checkout_group_id:
        sibling_orders = Order.objects.filter(
            customer=user,
            checkout_group_id=order.checkout_group_id
        ).exclude(id=order.id).select_related('shop')

    order_review = Review.objects.filter(order=order).first()
    shop_has_review = Review.objects.filter(shop=order.shop, user=user).exists()
    can_rate_order = is_customer and (order.status == Order.Status.COMPLETED) and (order_review is None) and (not shop_has_review)
    order_rating_criteria = order.shop.get_rating_criteria()

    context = {
        'order': order,
        'is_customer': is_customer,
        'is_shop_owner': is_shop_owner,
        'is_admin': is_admin,
        'sibling_orders': sibling_orders,
        'order_review': order_review,
        'can_rate_order': can_rate_order,
        'order_rating_criteria': order_rating_criteria,
    }
    return render(request, 'orders/order_detail.html', context)


@ensure_csrf_cookie
def web_nearby_shops(request):
    """
    Nearby Shops Discovery Page (/shops/nearby/):
    Interactive Leaflet map displaying verified community shops, distance calculation,
    category filters, search, and navigation directions.
    """
    all_categories = ShopCategory.objects.all().order_by('name')
    selected_category = request.GET.get('category', '').strip()
    search_query = request.GET.get('q', '').strip()
    radius = request.GET.get('radius', '10')

    try:
        radius_km = float(radius)
        if radius_km not in [1.0, 5.0, 10.0, 25.0, 50.0]:
            radius_km = 10.0
    except ValueError:
        radius_km = 10.0

    user_location = None
    default_lat = None
    default_lng = None

    if request.user.is_authenticated:
        user_loc = getattr(request.user, 'location', None)
        if user_loc and user_loc.latitude and user_loc.longitude and is_valid_coord(user_loc.latitude, user_loc.longitude):
            user_location = {
                'latitude': float(user_loc.latitude),
                'longitude': float(user_loc.longitude)
            }
            default_lat = float(user_loc.latitude)
            default_lng = float(user_loc.longitude)

    if not default_lat or not default_lng:
        first_shop = Shop.objects.filter(is_verified=True, latitude__isnull=False, longitude__isnull=False).first()
        if first_shop:
            default_lat = float(first_shop.latitude)
            default_lng = float(first_shop.longitude)
        else:
            default_lat = 10.8505
            default_lng = 76.2711

    context = {
        'all_categories': all_categories,
        'selected_category': int(selected_category) if selected_category.isdigit() else None,
        'search_query': search_query,
        'selected_radius': radius_km,
        'radius_options': [1, 5, 10, 25, 50],
        'user_location': user_location,
        'default_center_lat': default_lat,
        'default_center_lng': default_lng,
    }
    return render(request, 'shops/nearby_shops.html', context)


@login_required(login_url='web-login')
def web_shop_location_edit(request, shop_id):
    """
    Shop Location Edit Page (/dashboard/shop/<shop_id>/location/):
    Allows shop owners to pin/confirm their shop's GPS coordinates using Leaflet map or browser GPS.
    """
    shop = get_object_or_404(Shop, id=shop_id)

    # Ownership check
    if shop.owner != request.user and not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
        raise PermissionDenied("നിങ്ങൾക്ക് ഈ കടയുടെ ലൊക്കേഷൻ എഡിറ്റ് ചെയ്യാൻ അനുവാദമില്ല.")

    if request.method == 'POST':
        if request.POST.get('clear_location') == 'true':
            shop.latitude = None
            shop.longitude = None
            shop.save(update_fields=['latitude', 'longitude', 'updated_at'])
            messages.success(request, f"'{shop.name}'-ന്റെ ലൊക്കേഷൻ മാപ്പിൽ നിന്നും നീക്കം ചെയ്തു.")
            return redirect('shop-location-edit', shop_id=shop.id)

        raw_lat = request.POST.get('latitude', '').strip()
        raw_lng = request.POST.get('longitude', '').strip()
        address = request.POST.get('address', '').strip()

        if not raw_lat or not raw_lng or not is_valid_coord(raw_lat, raw_lng):
            messages.error(request, "സാധുവായ അക്ഷാംശവും രേഖാംശവും (Valid Latitude/Longitude) നൽകുക.")
            return redirect('shop-location-edit', shop_id=shop.id)

        shop.latitude = Decimal(raw_lat)
        shop.longitude = Decimal(raw_lng)
        if address:
            shop.address = address
        shop.save(update_fields=['latitude', 'longitude', 'address', 'updated_at'])

        messages.success(request, f"'{shop.name}'-ന്റെ ലൊക്കേഷൻ മാപ്പിൽ വിജയകരമായി രേഖപ്പെടുത്തി!")
        return redirect('shop-dashboard')

    has_location = bool(shop.latitude is not None and shop.longitude is not None)
    current_lat = float(shop.latitude) if has_location else 10.8505
    current_lng = float(shop.longitude) if has_location else 76.2711

    context = {
        'shop': shop,
        'has_location': has_location,
        'current_lat': current_lat,
        'current_lng': current_lng,
    }
    return render(request, 'shops/shop_location_edit.html', context)


@login_required(login_url='web-login')
def web_shop_hours_edit(request, shop_id):
    """
    Shop Working Hours Edit Page (/dashboard/shop/<shop_id>/hours/):
    Allows shop owners to configure 7-day weekly schedule (Opening, Closing, Holiday)
    and emergency Temporarily Closed status.
    Enforces strict Anti-BOLA ownership security.
    """
    shop = _get_manageable_shop_or_403(request.user, shop_id)

    day_meta = [
        (0, 'Monday', 'തിങ്കൾ (Monday)'),
        (1, 'Tuesday', 'ചൊവ്വ (Tuesday)'),
        (2, 'Wednesday', 'ബുധൻ (Wednesday)'),
        (3, 'Thursday', 'വ്യാഴം (Thursday)'),
        (4, 'Friday', 'വെള്ളി (Friday)'),
        (5, 'Saturday', 'ശനി (Saturday)'),
        (6, 'Sunday', 'ഞായർ (Sunday)'),
    ]

    if request.method == 'POST':
        is_temp_closed = request.POST.get('is_temporarily_closed') == 'on'
        temp_reason = request.POST.get('temporary_close_reason', '').strip()

        shop.is_temporarily_closed = is_temp_closed
        shop.temporary_close_reason = temp_reason
        if is_temp_closed:
            shop.is_open = False
        else:
            shop.is_open = True

        first_open_ot = None
        first_open_ct = None

        for day_idx, en_name, ml_name in day_meta:
            is_closed = request.POST.get(f'closed_{day_idx}') == 'on'
            ot_str = request.POST.get(f'open_time_{day_idx}', '').strip()
            ct_str = request.POST.get(f'close_time_{day_idx}', '').strip()

            ot = None
            ct = None
            if not is_closed:
                if ot_str:
                    try:
                        ot = datetime.strptime(ot_str, '%H:%M').time()
                    except ValueError:
                        pass
                if ct_str:
                    try:
                        ct = datetime.strptime(ct_str, '%H:%M').time()
                    except ValueError:
                        pass
                if ot and ct and first_open_ot is None:
                    first_open_ot = ot
                    first_open_ct = ct

            ShopWorkingHour.objects.update_or_create(
                shop=shop,
                day=day_idx,
                defaults={
                    'opening_time': ot,
                    'closing_time': ct,
                    'is_closed': is_closed,
                }
            )

        if first_open_ot and first_open_ct:
            shop.opening_time = first_open_ot
            shop.closing_time = first_open_ct

        shop.save()
        messages.success(request, f"'{shop.name}'-ന്റെ പ്രവർത്തന സമയം വിജയകരമായി അപ്‌ഡേറ്റ് ചെയ്തു.")
        return redirect('shop-dashboard')

    # GET request
    existing_hours = {h.day: h for h in shop.working_hours.all()}
    days_data = []
    for day_idx, en_name, ml_name in day_meta:
        h = existing_hours.get(day_idx)
        days_data.append({
            'day': day_idx,
            'name_en': en_name,
            'name_ml': ml_name,
            'is_closed': h.is_closed if h else (day_idx == 6),
            'opening_time': h.opening_time.strftime('%H:%M') if (h and h.opening_time) else ('09:00' if day_idx != 6 else ''),
            'closing_time': h.closing_time.strftime('%H:%M') if (h and h.closing_time) else ('20:00' if day_idx != 6 else ''),
        })

    context = {
        'shop': shop,
        'days_data': days_data,
        'is_temporarily_closed': shop.is_temporarily_closed,
        'temporary_close_reason': shop.temporary_close_reason,
    }
    return render(request, 'shops/shop_hours_edit.html', context)


# ==============================================================================
# LOCAL SERVICES DIRECTORY WEB ACTIONS
# ==============================================================================

@login_required(login_url='web-login')
def web_directory_submit(request):
    """
    Citizens can submit a local service to the directory (Plumber, Electrician, Taxi, etc.).
    Non-admins submit with is_verified=False (pending admin approval).
    Admins submit with is_verified=True directly.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    name = request.POST.get('name', '').strip()
    category = request.POST.get('category', '').strip()
    phone_number = request.POST.get('phone_number', '').strip()
    secondary_phone = request.POST.get('secondary_phone', '').strip()
    address_or_stand = request.POST.get('address_or_stand', '').strip()
    ward_number_val = request.POST.get('ward_number', '').strip()
    area_id = request.POST.get('area')
    is_emergency = request.POST.get('is_emergency_service') in ['true', '1', 'on', True]

    if not name or not category or not phone_number or not address_or_stand:
        messages.error(request, "ദയവായി പേര്, വിഭാഗം, ഫോൺ നമ്പർ, സ്റ്റാൻഡ്/വിലാസം എന്നിവ പൂരിപ്പിക്കുക.")
        return redirect(request.META.get('HTTP_REFERER') or 'user-dashboard')

    ward_number = None
    if ward_number_val:
        try:
            ward_number = int(ward_number_val)
        except ValueError:
            pass

    area = None
    if area_id:
        try:
            area = Area.objects.get(id=area_id)
        except Area.DoesNotExist:
            pass
    if not area:
        area = request.user.area

    is_admin = request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN
    is_verified = is_admin
    if not is_admin:
        is_emergency = False  # Only admins can designate emergency services

    DirectoryEntry.objects.create(
        name=name,
        category=category,
        phone_number=phone_number,
        secondary_phone=secondary_phone,
        address_or_stand=address_or_stand,
        ward_number=ward_number,
        area=area,
        is_emergency_service=is_emergency,
        is_verified=is_verified,
        submitted_by=request.user
    )

    if is_verified:
        messages.success(request, f"'{name}' സേവന ഡയറക്ടറിയിലേക്ക് വിജയകരമായി ചേർത്തു.")
    else:
        messages.success(request, f"'{name}' ഡയറക്ടറിയിൽ ചേർക്കാനുള്ള അപേക്ഷ സമർപ്പിച്ചു. അഡ്മിൻ പരിശോധിച്ച് ഉടൻ അംഗീകരിക്കുന്നതാണ്.")

    return redirect(request.META.get('HTTP_REFERER') or 'user-dashboard')


@login_required(login_url='web-login')
def web_admin_verify_directory(request, entry_id):
    """
    Super Admin verifies and approves a pending service directory entry.
    """
    if not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അധികാരമില്ല.")
        return redirect('home')

    if request.method != 'POST':
        return redirect('admin-dashboard')

    entry = get_object_or_404(DirectoryEntry, id=entry_id)
    entry.is_verified = True
    entry.save(update_fields=['is_verified'])

    notify_directory_status(entry, True, admin_user=request.user)
    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.DIRECTORY_APPROVE,
        target_type='DirectoryEntry',
        target_id=entry.id,
        target_identifier=entry.name,
        reason=f"Approved service directory entry {entry.name} ({entry.get_category_display()})"
    )

    messages.success(request, f"'{entry.name}' ({entry.get_category_display()}) സേവനത്തിന് വിജയകരമായി അംഗീകാരം നൽകി. പൊതുജനങ്ങൾക്ക് ഇപ്പോൾ കാണാം.")
    return redirect('admin-dashboard')


@login_required(login_url='web-login')
def web_admin_reject_directory(request, entry_id):
    """
    Super Admin rejects and removes a pending service directory entry.
    """
    if not (request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN):
        messages.error(request, "അധികാരമില്ല.")
        return redirect('home')

    if request.method != 'POST':
        return redirect('admin-dashboard')

    entry = get_object_or_404(DirectoryEntry, id=entry_id)
    name = entry.name

    notify_directory_status(entry, False, admin_user=request.user)
    log_audit(
        performed_by=request.user,
        action=AuditLog.Action.DIRECTORY_REJECT,
        target_type='DirectoryEntry',
        target_id=entry.id,
        target_identifier=name,
        reason=f"Rejected service directory entry {name}"
    )

    entry.delete()
    messages.info(request, f"'{name}' സേവന അപേക്ഷ നിരസിച്ചു/നീക്കം ചെയ്തു.")
    return redirect('admin-dashboard')


@login_required(login_url='web-login')
def web_directory_delete(request, entry_id):
    """
    Allows user to delete their own submitted directory entry, or admin to delete any entry.
    """
    if request.method != 'POST':
        return redirect('user-dashboard')

    entry = get_object_or_404(DirectoryEntry, id=entry_id)
    is_admin = request.user.is_staff or request.user.role == User.Role.SUPER_ADMIN
    if entry.submitted_by != request.user and not is_admin:
        messages.error(request, "ഈ സേവനം നീക്കം ചെയ്യാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")
        return redirect('user-dashboard')

    name = entry.name
    entry.delete()
    messages.success(request, f"'{name}' സേവന ഡയറക്ടറിയിൽ നിന്ന് നീക്കം ചെയ്തു.")
    referer = request.META.get('HTTP_REFERER')
    if referer and '/dashboard/' in referer:
        return redirect(referer)
    return redirect('user-dashboard')



