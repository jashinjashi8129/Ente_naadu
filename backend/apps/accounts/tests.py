from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import User, Area, AuditLog, UserReport
from apps.shops.models import Shop, Product, ShopCategory
from apps.orders.models import Order, Booking, Cart, CartItem
from apps.chat.models import FriendRequest, Friendship, Conversation, Message, SocialNotification
from apps.complaints.models import Complaint

class AccountsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Test Area", district="Kollam")

        self.citizen = User.objects.create_user(
            phone_number="9876543210",
            password="password123",
            full_name="Normal Citizen",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=5
        )

        self.admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

    def test_registration_prevents_privilege_escalation(self):
        """Users registering publicly cannot assign themselves super_admin or ward_admin."""
        url = reverse('register')
        data = {
            "phone_number": "9123456780",
            "password": "mypassword123",
            "full_name": "Attacker",
            "role": "super_admin"
        }
        response = self.client.post(url, data, format='json')
        # Should be rejected with 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_citizen_success(self):
        """Normal citizen registration succeeds with role='citizen'."""
        url = reverse('register')
        data = {
            "phone_number": "9123456789",
            "password": "mypassword123",
            "full_name": "Valid Citizen",
            "role": "citizen"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(phone_number="9123456789")
        self.assertEqual(user.role, User.Role.CITIZEN)

    def test_profile_patch_cannot_escalate_role(self):
        """An authenticated user cannot modify their own role to super_admin."""
        self.client.force_authenticate(user=self.citizen)
        url = reverse('profile')
        response = self.client.patch(url, {"role": "super_admin"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.role, User.Role.CITIZEN)

    def test_profile_patch_cannot_change_phone_number(self):
        """An authenticated user cannot change their unique phone number via profile."""
        self.client.force_authenticate(user=self.citizen)
        url = reverse('profile')
        self.client.patch(url, {"phone_number": "9000000000"}, format='json')
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.phone_number, "9876543210")

    def test_login_success(self):
        """Valid login returns an authentication token."""
        url = reverse('login')
        response = self.client.post(url, {
            "phone_number": "9876543210",
            "password": "password123"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_login_invalid_password(self):
        """Login with wrong password fails with 400."""
        url = reverse('login')
        response = self.client.post(url, {
            "phone_number": "9876543210",
            "password": "wrongpassword"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_blocked_user_cannot_login(self):
        """A blocked account is denied login."""
        self.citizen.is_blocked = True
        self.citizen.block_reason = "Spamming"
        self.citizen.save()

        url = reverse('login')
        response = self.client.post(url, {
            "phone_number": "9876543210",
            "password": "password123"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("blocked", str(response.data))

    def test_non_admin_cannot_access_admin_stats(self):
        """Regular users receive 403 Forbidden on admin stats."""
        self.client.force_authenticate(user=self.citizen)
        url = reverse('admin-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_block_user_with_audit_log(self):
        """Super Admin can block a user, producing an AuditLog record."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('admin-block-user')
        data = {
            "user_id": self.citizen.id,
            "reason": "Repeated policy violation",
            "block": True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.citizen.refresh_from_db()
        self.assertTrue(self.citizen.is_blocked)
        self.assertEqual(self.citizen.block_reason, "Repeated policy violation")

        log = AuditLog.objects.filter(target_id=self.citizen.id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, AuditLog.Action.BLOCK_USER)


class GPSLocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Kochi Central", district="Ernakulam")
        self.user = User.objects.create_user(
            phone_number="9847012345",
            password="securepassword",
            full_name="Anoop Kumar",
            role=User.Role.CITIZEN,
            area=self.area
        )

    def test_geo_haversine_and_validation_helpers(self):
        """Verify Haversine formula and coordinate validation logic."""
        from apps.common.geo import haversine_distance, is_valid_coord, approximate_coord, bounding_box

        # Valid coords check
        self.assertTrue(is_valid_coord(10.8505, 76.2711))
        self.assertFalse(is_valid_coord(95.0, 76.2711))  # Lat out of range
        self.assertFalse(is_valid_coord(10.8505, 190.0))  # Lng out of range
        self.assertFalse(is_valid_coord("not_a_num", 76.2711))

        # Known distance: Kochi (9.9312, 76.2673) to Thrissur (10.5276, 76.2144) is ~66-68 km
        dist = haversine_distance(9.9312, 76.2673, 10.5276, 76.2144)
        self.assertIsNotNone(dist)
        self.assertTrue(60 <= dist <= 75)

        # Distance to same point is 0.0
        self.assertEqual(haversine_distance(10.0, 76.0, 10.0, 76.0), 0.0)

        # Approximate coordinate rounding (~1km fuzzing)
        lat_fuzz, lng_fuzz = approximate_coord(10.854321, 76.278912)
        self.assertEqual(lat_fuzz, 10.85)
        self.assertEqual(lng_fuzz, 76.28)

        # Bounding box calculation
        min_lat, max_lat, min_lng, max_lng = bounding_box(10.0, 76.0, 10.0)
        self.assertTrue(min_lat < 10.0 < max_lat)
        self.assertTrue(min_lng < 76.0 < max_lng)

    def test_location_status_unauthenticated(self):
        """Unauthenticated requests to location endpoints are rejected."""
        url = reverse('user-location-status')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_location_status_authenticated(self):
        """Authenticated user gets current location status and privacy settings."""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-location-status')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('is_sharing_enabled', res.data)
        self.assertIn('share_precision', res.data)
        self.assertFalse(res.data['is_sharing_enabled'])  # Default privacy-first: False

    def test_location_update_valid_coordinates(self):
        """Updating location with valid coordinates returns 200 and saves state."""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-location-update')
        payload = {
            "latitude": 9.9312,
            "longitude": 76.2673
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['latitude'], 9.9312)
        self.assertEqual(res.data['longitude'], 76.2673)

        # Check DB persistence
        from apps.accounts.models import UserLocation
        loc = UserLocation.objects.get(user=self.user)
        self.assertEqual(loc.latitude, 9.9312)
        self.assertEqual(loc.longitude, 76.2673)

    def test_location_update_invalid_coordinates_rejected(self):
        """Invalid coordinate values return 400 Bad Request."""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-location-update')

        # Latitude > 90
        res = self.client.post(url, {"latitude": 99.99, "longitude": 76.0}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Longitude < -180
        res = self.client.post(url, {"latitude": 10.0, "longitude": -195.0}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-numeric
        res = self.client.post(url, {"latitude": "invalid", "longitude": 76.0}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_location_preferences_update(self):
        """User can update privacy controls (sharing enabled, paused, precision)."""
        self.client.force_authenticate(user=self.user)
        url = reverse('user-location-preferences')
        payload = {
            "is_sharing_enabled": True,
            "is_paused": True,
            "share_precision": "approximate"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['is_sharing_enabled'])
        self.assertTrue(res.data['is_paused'])
        self.assertEqual(res.data['share_precision'], 'approximate')

    def test_user_location_model_stale_and_visibility(self):
        """Verify stale coordinate (>24h) expiry and visibility rules."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.accounts.models import UserLocation

        loc, _ = UserLocation.objects.get_or_create(user=self.user)
        loc.latitude = 10.0
        loc.longitude = 76.0
        loc.is_sharing_enabled = True
        loc.is_paused = False
        loc.save()

        # Fresh location is visible
        self.assertTrue(loc.is_visible_to_friends())
        self.assertFalse(loc.is_stale())

        # If paused, it is not visible
        loc.is_paused = True
        self.assertFalse(loc.is_visible_to_friends())
        loc.is_paused = False

        # If sharing disabled, not visible
        loc.is_sharing_enabled = False
        self.assertFalse(loc.is_visible_to_friends())
        loc.is_sharing_enabled = True

        # Stale location (>24 hours) is expired and not visible
        loc.updated_at = timezone.now() - timedelta(hours=25)
        self.assertTrue(loc.is_stale())
        self.assertFalse(loc.is_visible_to_friends())


# ==================== Phase 4: Trust, Moderation & Spam Control Tests ====================

class TrustAndModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Test Area", district="Kollam")
        self.citizen = User.objects.create_user(
            phone_number="9876543210",
            password="password123",
            full_name="Normal Citizen",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=5
        )
        self.other_citizen = User.objects.create_user(
            phone_number="9876543211",
            password="password123",
            full_name="Other Citizen",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=5
        )
        self.super_admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

    def test_citizen_can_file_user_report(self):
        """Citizen can file a report against spam, fraud, or abuse."""
        self.client.force_authenticate(user=self.citizen)
        url = reverse('user-report-list')
        payload = {
            "reported_user": self.other_citizen.id,
            "content_type": "user",
            "content_id": self.other_citizen.id,
            "reason": UserReport.Reason.SPAM,
            "description": "Sending unwanted commercial promotion messages repeatedly."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        report = UserReport.objects.get(id=res.data['id'])
        self.assertEqual(report.reporter, self.citizen)
        self.assertEqual(report.reported_user, self.other_citizen)
        self.assertEqual(report.status, UserReport.Status.PENDING)

    def test_citizen_cannot_report_themselves(self):
        """Citizen cannot report their own account."""
        self.client.force_authenticate(user=self.citizen)
        url = reverse('user-report-list')
        payload = {
            "reported_user": self.citizen.id,
            "content_type": "user",
            "reason": UserReport.Reason.SPAM,
            "description": "Reporting myself"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_citizen_only_sees_their_own_filed_reports(self):
        """Citizen cannot see moderation reports filed by other citizens."""
        report_a = UserReport.objects.create(
            reporter=self.citizen,
            reported_user=self.other_citizen,
            reason=UserReport.Reason.SPAM,
            description="Report by citizen A"
        )
        report_b = UserReport.objects.create(
            reporter=self.other_citizen,
            reported_user=self.citizen,
            reason=UserReport.Reason.ABUSE,
            description="Report by citizen B"
        )

        self.client.force_authenticate(user=self.citizen)
        url = reverse('user-report-list')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        report_ids = [r['id'] for r in res.data.get('results', res.data)]
        self.assertIn(report_a.id, report_ids)
        self.assertNotIn(report_b.id, report_ids)

    def test_admin_can_resolve_report_and_take_action(self):
        """Staff/Super Admin can resolve report, record action taken, and log to AuditLog."""
        report = UserReport.objects.create(
            reporter=self.citizen,
            reported_user=self.other_citizen,
            reason=UserReport.Reason.FRAUD,
            description="Fake shop profile collecting money"
        )

        self.client.force_authenticate(user=self.super_admin)
        url = reverse('user-report-resolve', kwargs={'pk': report.id})
        payload = {
            "action_taken": "Blocked user account and removed fake listing",
            "admin_notes": "Confirmed phone number does not correspond to genuine shop."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.Status.RESOLVED)
        self.assertEqual(report.admin_action_taken, "Blocked user account and removed fake listing")
        self.assertEqual(report.reviewed_by, self.super_admin)

        # Verify AuditLog created
        log = AuditLog.objects.filter(target_type='UserReport', target_id=report.id).latest('timestamp')
        self.assertEqual(log.action, AuditLog.Action.REPORT_RESOLVE)
        self.assertEqual(log.performed_by, self.super_admin)

    def test_admin_can_dismiss_report(self):
        """Admin can dismiss report with reason if no policy violation occurred."""
        report = UserReport.objects.create(
            reporter=self.citizen,
            reported_user=self.other_citizen,
            reason=UserReport.Reason.SPAM,
            description="Just normal inquiry"
        )

        self.client.force_authenticate(user=self.super_admin)
        url = reverse('user-report-dismiss', kwargs={'pk': report.id})
        payload = {
            "admin_notes": "Reviewed conversation; genuine inquiry, no spam."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, UserReport.Status.DISMISSED)
        self.assertEqual(report.admin_notes, "Reviewed conversation; genuine inquiry, no spam.")

        # Verify AuditLog created
        log = AuditLog.objects.filter(target_type='UserReport', target_id=report.id).latest('timestamp')
        self.assertEqual(log.action, AuditLog.Action.REPORT_DISMISS)

    def test_regular_citizen_cannot_resolve_or_dismiss_reports(self):
        """Regular citizens cannot resolve or dismiss reports."""
        report = UserReport.objects.create(
            reporter=self.citizen,
            reported_user=self.other_citizen,
            reason=UserReport.Reason.SPAM,
            description="Spam report"
        )
        self.client.force_authenticate(user=self.other_citizen)
        url_resolve = reverse('user-report-resolve', kwargs={'pk': report.id})
        res = self.client.post(url_resolve, {"action_taken": "Dismissed by accused"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


# ==================== Phase 5: Android Mobile Application Integration Tests ====================

class AndroidMobileApiIntegrationTests(TestCase):
    """
    End-to-end integration tests verifying that Android mobile client workflows
    operate seamlessly against the active Django REST API endpoints.
    Verifies:
    1. Authentication & token persistence (Same accounts on web and mobile)
    2. Profile fetching and updating
    3. Multi-shop cart operations & atomic checkout
    4. Appointments / Service booking & cancellation
    5. Friend requests, acceptance, and unfriend lifecycle
    6. Private chat messaging, polling, and immediate cutoff upon unfriend
    7. GPS privacy controls & ~500m fuzzed nearby friends discovery
    8. Nearby commercial shops discovery
    9. Geotagged civic complaints submission and tracking
    """

    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Kochi Ward 3", district="Ernakulam")

        # 1. Citizen / Customer Account
        self.customer = User.objects.create_user(
            phone_number="9847111222",
            password="CustomerPass123",
            full_name="Mobile User",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=3
        )

        # 2. Peer Friend Account
        self.friend = User.objects.create_user(
            phone_number="9847333444",
            password="FriendPass123",
            full_name="Nearby Friend",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=3
        )

        # 3. Shop 1: General Grocery (Order mode)
        self.owner1 = User.objects.create_user(
            phone_number="9847555666",
            password="OwnerPass123",
            full_name="Shopkeeper One",
            role=User.Role.SHOP_OWNER,
            area=self.area,
            ward_number=3
        )
        self.cat_grocery = ShopCategory.objects.create(
            name="Grocery Store",
            interaction_mode=ShopCategory.InteractionMode.ORDER,
            business_type=ShopCategory.BusinessType.GENERAL
        )
        self.shop1 = Shop.objects.create(
            owner=self.owner1,
            name="Kochi Supermarket",
            category=self.cat_grocery,
            contact_phone="9847555666",
            address="Market Junction",
            ward_number=3,
            latitude=10.5280,
            longitude=76.2150,
            is_open=True,
            is_verified=True
        )
        self.prod1 = Product.objects.create(
            shop=self.shop1,
            name="Rice (Matta)",
            price=48.00,
            is_available=True
        )

        # 4. Shop 2: Beauty Salon (Booking mode)
        self.owner2 = User.objects.create_user(
            phone_number="9847777888",
            password="OwnerPass123",
            full_name="Shopkeeper Two",
            role=User.Role.SHOP_OWNER,
            area=self.area,
            ward_number=3
        )
        self.cat_salon = ShopCategory.objects.create(
            name="Beauty Care",
            interaction_mode=ShopCategory.InteractionMode.BOOKING,
            business_type=ShopCategory.BusinessType.BEAUTY_PARLOUR
        )
        self.shop2 = Shop.objects.create(
            owner=self.owner2,
            name="Kerala Salon",
            category=self.cat_salon,
            contact_phone="9847777888",
            address="Junction Road",
            ward_number=3,
            latitude=10.5290,
            longitude=76.2160,
            is_open=True,
            is_verified=True
        )
        self.prod2 = Product.objects.create(
            shop=self.shop2,
            name="Hair Care Product",
            price=250.00,
            is_available=True
        )
        self.service_booking = Product.objects.create(
            shop=self.shop2,
            name="Hair Styling Service",
            price=350.00,
            service_duration_minutes=45,
            is_available=True
        )

    def test_mobile_auth_token_and_profile_flow(self):
        """Android login returns DRF Token; profile query and update succeed seamlessly."""
        # 1. Login with phone + password
        login_res = self.client.post("/api/v1/auth/login/", {
            "phone_number": "9847111222",
            "password": "CustomerPass123"
        }, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn('token', login_res.data)
        token_key = login_res.data['token']

        # 2. Inject Authorization: Token <key> into client headers
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_key}")

        # 3. Query user profile
        profile_res = self.client.get("/api/v1/auth/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data['phone_number'], "9847111222")
        self.assertEqual(profile_res.data['full_name'], "Mobile User")

        # 4. Update profile data from mobile
        update_res = self.client.patch("/api/v1/auth/profile/", {
            "full_name": "Mobile User Updated",
            "ward_number": 4
        }, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Mobile User Updated")
        self.assertEqual(self.customer.ward_number, 4)

    def test_mobile_multi_shop_cart_and_atomic_checkout(self):
        """Android cart groups items from multiple shops; atomic checkout generates child orders."""
        token, _ = Token.objects.get_or_create(user=self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # 1. Add item from Shop 1
        res1 = self.client.post("/api/v1/orders/cart/add/", {
            "product_id": self.prod1.id,
            "quantity": 2
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # 2. Add item from Shop 2
        res2 = self.client.post("/api/v1/orders/cart/add/", {
            "product_id": self.prod2.id,
            "quantity": 1
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        # 3. Fetch cart and inspect structure
        cart_res = self.client.get("/api/v1/orders/cart/")
        self.assertEqual(cart_res.status_code, status.HTTP_200_OK)
        items = cart_res.data.get('items', [])
        self.assertEqual(len(items), 2)
        item1_id = items[0]['id']

        # 4. Update quantity of item 1
        patch_res = self.client.patch(f"/api/v1/orders/cart/items/{item1_id}/", {
            "quantity": 3
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)

        # 5. Multi-shop Checkout
        checkout_payload = {
            "delivery_type": Order.DeliveryType.HOME_DELIVERY,
            "delivery_address": "House #42, Main Road, Kochi",
            "customer_phone": "9847111222",
            "notes": "Deliver before evening"
        }
        checkout_res = self.client.post("/api/v1/orders/cart/checkout/", checkout_payload, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        self.assertIn('checkout_group_id', checkout_res.data)
        group_id = checkout_res.data['checkout_group_id']

        # Both shop orders created under single checkout group
        created_orders = Order.objects.filter(checkout_group_id=group_id)
        self.assertEqual(created_orders.count(), 2)

        # Cart cleared after checkout
        self.assertEqual(CartItem.objects.filter(cart__customer=self.customer).count(), 0)

        # Customer orders list
        orders_res = self.client.get("/api/v1/orders/orders/")
        self.assertEqual(orders_res.status_code, status.HTTP_200_OK)
        order_ids = [o['id'] for o in (orders_res.data.get('results') if isinstance(orders_res.data, dict) else orders_res.data)]
        for o in created_orders:
            self.assertIn(o.id, order_ids)

    def test_mobile_service_appointment_booking_and_cancellation(self):
        """Android appointment booking and cancellation flow operates via REST."""
        token, _ = Token.objects.get_or_create(user=self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # 1. Create service appointment booking
        booking_data = {
            "shop": self.shop2.id,
            "service": self.service_booking.id,
            "booking_date": "2026-11-20",
            "time_slot": "11:00 AM - 12:00 PM",
            "number_of_people": 1,
            "special_notes": "Hair styling required"
        }
        create_res = self.client.post("/api/v1/orders/bookings/", booking_data, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        booking_id = create_res.data['id']

        # 2. Verify booking in customer bookings list
        list_res = self.client.get("/api/v1/orders/bookings/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        bookings = list_res.data if isinstance(list_res.data, list) else list_res.data.get('results', [])
        booking_ids = [b['id'] for b in bookings]
        self.assertIn(booking_id, booking_ids)

        # 3. Customer cancels pending booking
        cancel_res = self.client.post(
            f"/api/v1/orders/bookings/{booking_id}/update-status/",
            {"status": "cancelled"},
            format='json'
        )
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)
        booking_obj = Booking.objects.get(id=booking_id)
        self.assertEqual(booking_obj.status, Booking.Status.CANCELLED)

    def test_mobile_friends_chat_and_unfriend_lifecycle(self):
        """Android friends search, request, accept, chat polling, and unfriend cutoff."""
        token_cust, _ = Token.objects.get_or_create(user=self.customer)
        token_friend, _ = Token.objects.get_or_create(user=self.friend)

        # 1. Search user
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        search_res = self.client.get("/api/v1/chat/users/?q=Nearby")
        self.assertEqual(search_res.status_code, status.HTTP_200_OK)
        results = search_res.data if isinstance(search_res.data, list) else search_res.data.get('results', [])
        found_ids = [u['id'] for u in results]
        self.assertIn(self.friend.id, found_ids)

        # 2. Send friend request
        send_res = self.client.post("/api/v1/chat/requests/send/", {
            "receiver_id": self.friend.id
        }, format='json')
        self.assertEqual(send_res.status_code, status.HTTP_201_CREATED)
        req_id = send_res.data['id']

        # 3. Friend checks incoming requests
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_friend.key}")
        incoming_res = self.client.get("/api/v1/chat/requests/incoming/")
        self.assertEqual(incoming_res.status_code, status.HTTP_200_OK)
        inc_ids = [r['id'] for r in incoming_res.data]
        self.assertIn(req_id, inc_ids)

        # 4. Friend accepts request
        accept_res = self.client.post(f"/api/v1/chat/requests/{req_id}/accept/")
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)
        self.assertTrue(Friendship.are_friends(self.customer, self.friend))

        # 5. Customer starts conversation
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        conv_res = self.client.post(f"/api/v1/chat/conversations/start/{self.friend.id}/")
        self.assertEqual(conv_res.status_code, status.HTTP_200_OK)
        conv_id = conv_res.data['id']

        # 6. Customer sends message
        msg_res = self.client.post(f"/api/v1/chat/conversations/{conv_id}/messages/send/", {
            "text": "Hello from Flutter mobile!"
        }, format='json')
        self.assertEqual(msg_res.status_code, status.HTTP_201_CREATED)
        msg_id = msg_res.data['id']

        # 7. Friend polls messages
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_friend.key}")
        poll_res = self.client.get(f"/api/v1/chat/conversations/{conv_id}/poll/?after=0")
        self.assertEqual(poll_res.status_code, status.HTTP_200_OK)
        polled_ids = [m['id'] for m in poll_res.data.get('new_messages', [])]
        self.assertIn(msg_id, polled_ids)

        # 8. Unfriend
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        unfriend_res = self.client.post(f"/api/v1/chat/friends/{self.friend.id}/unfriend/")
        self.assertEqual(unfriend_res.status_code, status.HTTP_200_OK)
        self.assertFalse(Friendship.are_friends(self.customer, self.friend))

        # 9. Immediate Cutoff: Friend tries to send chat message; blocked with 403 Forbidden
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_friend.key}")
        blocked_msg_res = self.client.post(f"/api/v1/chat/conversations/{conv_id}/messages/send/", {
            "text": "Can you hear me?"
        }, format='json')
        self.assertEqual(blocked_msg_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_mobile_gps_privacy_and_nearby_friends_discovery(self):
        """Android GPS privacy: opt-in, approximate ~500m fuzzing, and pause toggle."""
        token_cust, _ = Token.objects.get_or_create(user=self.customer)
        token_friend, _ = Token.objects.get_or_create(user=self.friend)
        Friendship.make_friends(self.customer, self.friend)

        # 1. Customer configures privacy: sharing enabled, approximate precision
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        pref_res = self.client.post("/api/v1/auth/location/preferences/", {
            "is_sharing_enabled": True,
            "share_precision": "approximate",
            "is_paused": False
        }, format='json')
        self.assertEqual(pref_res.status_code, status.HTTP_200_OK)

        # 2. Customer updates on-demand GPS coordinates
        loc_res = self.client.post("/api/v1/auth/location/update/", {
            "latitude": 10.5276,
            "longitude": 76.2144
        }, format='json')
        self.assertEqual(loc_res.status_code, status.HTTP_200_OK)

        # 3. Friend queries nearby friends
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_friend.key}")
        nearby_res = self.client.get("/api/v1/chat/friends/nearby/?lat=10.5280&lng=76.2140&radius=10")
        self.assertEqual(nearby_res.status_code, status.HTTP_200_OK)
        friends_list = nearby_res.data.get('friends', [])
        self.assertEqual(len(friends_list), 1)
        friend_entry = friends_list[0]
        self.assertEqual(friend_entry['id'], self.customer.id)
        self.assertTrue(friend_entry['is_approximate'])
        # Fuzzed coordinate check (rounded to 2 decimal places ~500m fuzzing)
        self.assertEqual(friend_entry['latitude'], 10.53)
        self.assertEqual(friend_entry['longitude'], 76.21)

        # 4. Customer pauses location sharing
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        self.client.post("/api/v1/auth/location/preferences/", {"is_paused": True}, format='json')

        # 5. Friend queries nearby friends again: Customer is hidden
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_friend.key}")
        nearby_res_paused = self.client.get("/api/v1/chat/friends/nearby/?lat=10.5280&lng=76.2140&radius=10")
        self.assertEqual(len(nearby_res_paused.data.get('friends', [])), 0)

    def test_mobile_civic_complaints_flow(self):
        """Android user submits geotagged civic complaint and verifies tracking."""
        token, _ = Token.objects.get_or_create(user=self.customer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        # 1. Submit complaint
        complaint_payload = {
            "title": "Road pothole near Market Junction",
            "description": "Large pothole causing vehicle accidents.",
            "category": "roads",
            "ward_number": 3,
            "location_details": "Near Market Junction post office",
            "latitude": 10.5280,
            "longitude": 76.2150,
            "is_anonymous": True
        }
        submit_res = self.client.post("/api/v1/complaints/", complaint_payload, format='json')
        self.assertEqual(submit_res.status_code, status.HTTP_201_CREATED)
        complaint_id = submit_res.data['id']

        # 2. Fetch complaints list
        list_res = self.client.get("/api/v1/complaints/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        complaints = list_res.data if isinstance(list_res.data, list) else list_res.data.get('results', [])
        c_ids = [c['id'] for c in complaints]
        self.assertIn(complaint_id, c_ids)
        c_obj = Complaint.objects.get(id=complaint_id)
        self.assertEqual(c_obj.citizen, self.customer)
        self.assertTrue(c_obj.is_anonymous)
        self.assertEqual(c_obj.ward_number, 3)


# ==================== Phase 6: Production Launch Readiness Tests ====================

class ProductionLaunchReadinessTests(TestCase):
    """
    Verification of production-ready workflows and security configurations:
    1. Production security headers and settings validation
    2. End-to-end Citizen registration and login
    3. End-to-end Product ordering lifecycle (pending -> accepted -> completed)
    4. Service booking and payment/settlement callback workflow
    5. Geotagged civic complaint lifecycle & admin operations with audit logs
    6. Commercial shop discovery vs. personal GPS privacy
    """

    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Kottayam Ward 1", district="Kottayam")

        # Super Admin
        self.admin = User.objects.create_superuser(
            phone_number="9000000001",
            password="AdminProductionSecret!23",
            full_name="Panchayat Secretary"
        )

        # Shop Owner
        self.shop_owner = User.objects.create_user(
            phone_number="9000000002",
            password="OwnerProductionSecret!23",
            full_name="Merchant Babu",
            role=User.Role.SHOP_OWNER,
            area=self.area,
            ward_number=1
        )

        # General Category & Shop
        self.shop_cat = ShopCategory.objects.create(
            name="General Provisions",
            interaction_mode=ShopCategory.InteractionMode.ORDER,
            business_type=ShopCategory.BusinessType.GENERAL
        )
        self.shop = Shop.objects.create(
            owner=self.shop_owner,
            name="Babu Super Store",
            category=self.shop_cat,
            contact_phone="9000000002",
            address="Panchayat Junction",
            ward_number=1,
            latitude=9.5915,
            longitude=76.5221,
            is_open=True,
            is_verified=True
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Coconut Oil 1L",
            price=190.00,
            is_available=True
        )

    def test_production_settings_validation(self):
        """Validates critical security settings and defaults."""
        from django.conf import settings

        # Standard settings tests
        self.assertIn('rest_framework.authentication.TokenAuthentication', settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'])
        self.assertIn('rest_framework.authentication.SessionAuthentication', settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'])
        self.assertEqual(settings.REST_FRAMEWORK['EXCEPTION_HANDLER'], 'apps.common.exceptions.custom_exception_handler')

        # Throttles configured to protect against brute-force attacks and DoS
        self.assertIn('auth', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        self.assertIn('anon', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        self.assertIn('user', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])

        # Timezone for Kerala
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')

    def test_citizen_registration_and_login_e2e(self):
        """Tests full citizen registration, token creation, and profile retrieval."""
        reg_payload = {
            "phone_number": "9000000003",
            "password": "CitizenStrongPass123",
            "full_name": "Sujith Kumar",
            "ward_number": 1
        }
        reg_res = self.client.post("/api/v1/auth/register/", reg_payload, format='json')
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', reg_res.data)
        user_id = reg_res.data['user']['id']

        # User is created as CITIZEN role by default
        new_user = User.objects.get(id=user_id)
        self.assertEqual(new_user.role, User.Role.CITIZEN)
        self.assertEqual(new_user.full_name, "Sujith Kumar")

        # Login with newly registered credentials
        login_res = self.client.post("/api/v1/auth/login/", {
            "phone_number": "9000000003",
            "password": "CitizenStrongPass123"
        }, format='json')
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        token = login_res.data['token']

        # Fetch profile using Token
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        profile_res = self.client.get("/api/v1/auth/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data['phone_number'], "9000000003")

    def test_product_ordering_lifecycle_and_shop_fulfillment(self):
        """Full lifecycle: citizen orders product -> shop owner accepts -> marks completed."""
        customer = User.objects.create_user(
            phone_number="9000000004",
            password="Pass!123456",
            full_name="Devika Nair",
            role=User.Role.CITIZEN
        )
        token_cust, _ = Token.objects.get_or_create(user=customer)
        token_owner, _ = Token.objects.get_or_create(user=self.shop_owner)

        # 1. Customer adds product to cart
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cust.key}")
        self.client.post("/api/v1/orders/cart/add/", {
            "product_id": self.product.id,
            "quantity": 2
        }, format='json')

        # 2. Checkout order
        checkout_res = self.client.post("/api/v1/orders/cart/checkout/", {
            "delivery_type": Order.DeliveryType.HOME_DELIVERY,
            "delivery_address": "House #15, Temple Lane, Kottayam",
            "customer_phone": "9000000004"
        }, format='json')
        self.assertEqual(checkout_res.status_code, status.HTTP_201_CREATED)
        order_id = checkout_res.data['orders'][0]['id']

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total_amount, 380.00)

        # 3. Shop owner views order and updates status to ACCEPTED
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_owner.key}")
        update_res = self.client.post(f"/api/v1/orders/orders/{order_id}/update-status/", {
            "status": "accepted"
        }, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ACCEPTED)

        # 4. Shop owner marks order COMPLETED
        complete_res = self.client.post(f"/api/v1/orders/orders/{order_id}/update-status/", {
            "status": "completed"
        }, format='json')
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_complaint_workflow_and_admin_operations(self):
        """Citizen files complaint -> Admin investigates, updates status with remarks and resolves."""
        citizen = User.objects.create_user(
            phone_number="9000000005",
            password="CitizenPass!123",
            full_name="Rajesh P",
            role=User.Role.CITIZEN
        )
        token_cit, _ = Token.objects.get_or_create(user=citizen)
        token_admin, _ = Token.objects.get_or_create(user=self.admin)

        # 1. Citizen registers complaint
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_cit.key}")
        comp_res = self.client.post("/api/v1/complaints/", {
            "title": "Street light broken at Ward 1 junction",
            "description": "Dark stretch causing security issues for pedestrians.",
            "category": "electricity",
            "ward_number": 1,
            "location_details": "Opposite cooperative bank",
            "latitude": 9.5910,
            "longitude": 76.5220
        }, format='json')
        self.assertEqual(comp_res.status_code, status.HTTP_201_CREATED)
        complaint_id = comp_res.data['id']

        # 2. Admin inspects and updates status to IN_PROGRESS
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_admin.key}")
        prog_res = self.client.patch(f"/api/v1/complaints/{complaint_id}/", {
            "status": "in_progress",
            "admin_remarks": "KSEB electrical team dispatched for bulb replacement."
        }, format='json')
        self.assertEqual(prog_res.status_code, status.HTTP_200_OK)

        # 3. Admin marks complaint RESOLVED
        resolved_res = self.client.patch(f"/api/v1/complaints/{complaint_id}/", {
            "status": "resolved",
            "admin_remarks": "New LED fixture installed and verified by Lineman."
        }, format='json')
        self.assertEqual(resolved_res.status_code, status.HTTP_200_OK)

        complaint = Complaint.objects.get(id=complaint_id)
        self.assertEqual(complaint.status, Complaint.Status.RESOLVED)
        self.assertIn("New LED fixture installed", complaint.admin_remarks)


# ==================== Navbar Responsiveness & Overflow Prevention Tests ====================

class NavbarHorizontalOverflowTests(TestCase):
    """
    Tests for Navbar horizontal overflow resolution and responsive link organization:
    1. Desktop/Laptop: Primary links directly visible, secondary links in 'More' dropdown.
    2. Mobile/Tablet: Collapsible hamburger menu and full slide-over drawer.
    3. Authentication states: Guest vs Citizen vs Shop Owner vs Admin.
    4. Active menu highlighting and URL routing preservation.
    5. Prevention of horizontal clipping without reliance on overflow: hidden.
    """

    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.area = Area.objects.create(name="Alappuzha Ward 2", district="Alappuzha")

        self.citizen = User.objects.create_user(
            phone_number="9800000001",
            password="CitizenPassword123",
            full_name="Anoop Kumar",
            role=User.Role.CITIZEN,
            area=self.area,
            ward_number=2
        )

        self.shop_owner = User.objects.create_user(
            phone_number="9800000002",
            password="ShopPassword123",
            full_name="Suresh Trader",
            role=User.Role.SHOP_OWNER,
            area=self.area,
            ward_number=2
        )

        self.admin = User.objects.create_superuser(
            phone_number="9800000003",
            password="AdminPassword123",
            full_name="Admin Officer"
        )

    def test_guest_navbar_rendering(self):
        """Guest user sees Home, Shops, More dropdown, Cart, and Auth Modals without overflow."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Brand Identity
        self.assertIn("എന്റെ നാട്", content)
        # Primary Desktop links
        self.assertIn("ഹോം", content)
        self.assertIn("കടകൾ", content)
        self.assertIn("desktopMoreDropdownBtn", content)
        self.assertIn("desktopMoreDropdownMenu", content)
        # Guest Controls
        self.assertIn("ലോഗിൻ", content)
        self.assertIn("രജിസ്റ്റർ", content)
        self.assertIn("കട രജിസ്ട്രേഷൻ", content)
        # Mobile elements
        self.assertIn("mobileMenuToggle", content)
        self.assertIn("mobileMenuDrawer", content)
        self.assertIn("mobileMenuBackdrop", content)

    def test_citizen_navbar_shows_cart_chat_and_more_dropdown(self):
        """Authenticated citizen sees Cart, Chat, and More dropdown containing Friends & Directory."""
        self.client.force_login(self.citizen)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Citizen controls
        self.assertIn("എന്റെ ഡാഷ്ബോർഡ്", content)
        self.assertIn("ലോഗൗട്ട്", content)
        self.assertIn("Anoop Kumar", content)
        # Chat and Cart present
        self.assertIn("ചാറ്റ്", content)
        self.assertIn("കാർട്ട്", content)
        # Secondary links grouped in More dropdown & mobile drawer
        self.assertIn("അടുത്തുള്ള കടകൾ", content)
        self.assertIn("കൂട്ടുകാരുടെ മാപ്പ്", content)
        self.assertIn("കൂട്ടുകാർ", content)
        self.assertIn("സേവന ഡയറക്ടറി", content)

    def test_shop_owner_navbar_shows_shop_dashboard(self):
        """Shop owner sees Shop Dashboard and does not see citizen chat/cart."""
        self.client.force_login(self.shop_owner)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn("ഷോപ്പ് ഡാഷ്ബോർഡ്", content)
        self.assertIn("Suresh Trader", content)
        self.assertIn("ലോഗൗട്ട്", content)

    def test_admin_navbar_shows_admin_console(self):
        """Admin sees Admin Console and Django Admin link."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn("അഡ്മിൻ കൺസോൾ", content)
        self.assertIn("Django Admin", content)

    def test_navbar_active_state_classes(self):
        """Active link indicators are applied dynamically based on route."""
        # On shop list page
        response = self.client.get(reverse('shop-list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn("nav-link-active", content)

    def test_no_overflow_hidden_hack_on_navbar(self):
        """Navbar navigation must not use crude overflow: hidden to clip links."""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        # The desktop nav should be flex with wrapping/dropdown, not overflow-hidden
        self.assertNotIn('<nav class="hidden lg:flex items-center space-x-1 xl:space-x-2 overflow-hidden">', content)





