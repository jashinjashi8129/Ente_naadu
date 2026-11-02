from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Area, AuditLog
from apps.shops.models import ShopCategory, Shop, Product
from apps.chat.models import SocialNotification
from .models import Order, OrderItem, Booking, ServiceRequest

class OrdersSecurityAndIntegrityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Central Area", district="Alappuzha")

        self.owner = User.objects.create_user(
            phone_number="9800000010",
            password="password123",
            full_name="Hotel Owner",
            role=User.Role.SHOP_OWNER
        )

        self.customer = User.objects.create_user(
            phone_number="9800000020",
            password="password123",
            full_name="Customer User",
            role=User.Role.CITIZEN
        )

        self.other_user = User.objects.create_user(
            phone_number="9800000030",
            password="password123",
            full_name="Other User",
            role=User.Role.CITIZEN
        )

        self.category = ShopCategory.objects.create(
            name="Restaurant",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )

        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Kerala Meals",
            category=self.category,
            area=self.area,
            ward_number=2,
            address="Near Bus Stand",
            contact_phone="9800000010",
            is_verified=True,
            is_open=True
        )

        self.product = Product.objects.create(
            shop=self.shop,
            name="Meals with Fish Curry",
            price=120.00,
            unit="1 plate",
            is_available=True
        )

    def test_order_creation_success(self):
        """Customer creates order, total_amount is calculated accurately."""
        self.client.force_authenticate(user=self.customer)
        url = "/api/v1/orders/orders/"
        data = {
            "shop_id": self.shop.id,
            "delivery_type": "pickup",
            "items": [
                {"product_id": self.product.id, "quantity": 2}
            ]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.total_amount, 240.00)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_order_creation_closed_shop_rejected(self):
        """Orders placed to closed shops are rejected with 400 Bad Request."""
        self.shop.is_open = False
        self.shop.save()

        self.client.force_authenticate(user=self.customer)
        url = "/api/v1/orders/orders/"
        data = {
            "shop_id": self.shop.id,
            "items": [{"product_id": self.product.id, "quantity": 1}]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_order_creation_unavailable_product_rejected(self):
        """Orders for out of stock products are rejected without creating an order."""
        self.product.is_available = False
        self.product.save()

        self.client.force_authenticate(user=self.customer)
        url = "/api/v1/orders/orders/"
        data = {
            "shop_id": self.shop.id,
            "items": [{"product_id": self.product.id, "quantity": 1}]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_customer_cannot_patch_status_to_completed(self):
        """Customer cannot directly modify order status to completed via PATCH."""
        order = Order.objects.create(
            customer=self.customer,
            customer_phone=self.customer.phone_number,
            shop=self.shop,
            total_amount=120.00,
            status=Order.Status.PENDING
        )

        self.client.force_authenticate(user=self.customer)
        url = f"/api/v1/orders/orders/{order.id}/"
        response = self.client.patch(url, {"status": "completed"}, format='json')
        # Direct modification of orders is forbidden for customers
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])
        order.refresh_from_db()
        # Even if 200, status is read_only and remains PENDING
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_customer_cannot_delete_order(self):
        """Customers cannot delete order records."""
        order = Order.objects.create(
            customer=self.customer,
            customer_phone=self.customer.phone_number,
            shop=self.shop,
            total_amount=120.00,
            status=Order.Status.PENDING
        )

        self.client.force_authenticate(user=self.customer)
        url = f"/api/v1/orders/orders/{order.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Order.objects.filter(id=order.id).exists())

    def test_customer_can_cancel_pending_order_only(self):
        """Customer can cancel while status is pending, but not after accepted."""
        order = Order.objects.create(
            customer=self.customer,
            customer_phone=self.customer.phone_number,
            shop=self.shop,
            total_amount=120.00,
            status=Order.Status.PENDING
        )

        self.client.force_authenticate(user=self.customer)
        url = f"/api/v1/orders/orders/{order.id}/update-status/"
        response = self.client.post(url, {"status": "cancelled"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # Once accepted, customer cannot cancel
        order.status = Order.Status.ACCEPTED
        order.save()
        response = self.client.post(url, {"status": "cancelled"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MultiShopCartAndCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="South Ward", district="Alappuzha")

        # Shop 1: Medical Shop
        self.med_owner = User.objects.create_user(
            phone_number="9800000041",
            password="password123",
            full_name="Med Owner",
            role=User.Role.SHOP_OWNER
        )
        self.med_cat = ShopCategory.objects.create(name="Medical Shop", interaction_mode=ShopCategory.InteractionMode.ORDER)
        self.med_shop = Shop.objects.create(
            owner=self.med_owner,
            name="City Pharmacy",
            category=self.med_cat,
            area=self.area,
            ward_number=1,
            contact_phone="9800000041",
            is_verified=True,
            is_open=True
        )
        self.paracetamol = Product.objects.create(
            shop=self.med_shop,
            name="Paracetamol 650mg",
            price=30.00,
            discount_price=25.00,
            unit="1 strip",
            is_available=True,
            requires_prescription=False
        )
        self.antibiotic = Product.objects.create(
            shop=self.med_shop,
            name="Amoxicillin 500mg",
            price=110.00,
            unit="1 strip",
            is_available=True,
            requires_prescription=True,
            expiry_info="Exp 12/2027"
        )

        # Shop 2: Grocery Shop
        self.grocery_owner = User.objects.create_user(
            phone_number="9800000042",
            password="password123",
            full_name="Grocery Owner",
            role=User.Role.SHOP_OWNER
        )
        self.groc_cat = ShopCategory.objects.create(name="Grocery Store", interaction_mode=ShopCategory.InteractionMode.ORDER)
        self.groc_shop = Shop.objects.create(
            owner=self.grocery_owner,
            name="Green Valley Grocers",
            category=self.groc_cat,
            area=self.area,
            ward_number=1,
            contact_phone="9800000042",
            is_verified=True,
            is_open=True
        )
        self.rice = Product.objects.create(
            shop=self.groc_shop,
            name="Matta Rice",
            price=50.00,
            unit="1 kg",
            is_available=True
        )

        # Customer User
        self.customer = User.objects.create_user(
            phone_number="9800000050",
            password="password123",
            full_name="Anoop Kumar",
            role=User.Role.CITIZEN
        )

    def test_add_items_from_multiple_shops_to_cart(self):
        """Customer can add items from different shops into a unified cart."""
        self.client.force_authenticate(user=self.customer)

        # Add 2 strips of Paracetamol (City Pharmacy)
        res1 = self.client.post("/api/v1/orders/cart/add/", {"product_id": self.paracetamol.id, "quantity": 2}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Add 3 kg of Matta Rice (Green Valley Grocers)
        res2 = self.client.post("/api/v1/orders/cart/add/", {"product_id": self.rice.id, "quantity": 3}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        # Verify unified cart totals and shop grouping
        res_cart = self.client.get("/api/v1/orders/cart/")
        self.assertEqual(res_cart.status_code, status.HTTP_200_OK)
        data = res_cart.data
        self.assertEqual(data['total_items'], 5) # 2 + 3

        # Paracetamol uses discount_price (25.00 * 2 = 50.00)
        # Rice uses regular price (50.00 * 3 = 150.00)
        # Total = 200.00
        self.assertEqual(float(data['total_amount']), 200.00)

        grouped = data['grouped_by_shop']
        self.assertEqual(len(grouped), 2)
        shops_in_group = [g['shop_id'] for g in grouped]
        self.assertIn(self.med_shop.id, shops_in_group)
        self.assertIn(self.groc_shop.id, shops_in_group)

    def test_checkout_splits_orders_per_shop_with_group_id(self):
        """Checkout atomically creates distinct Order records per shop with a shared checkout_group_id."""
        self.client.force_authenticate(user=self.customer)

        # Add items to cart
        self.client.post("/api/v1/orders/cart/add/", {"product_id": self.paracetamol.id, "quantity": 2}, format='json')
        self.client.post("/api/v1/orders/cart/add/", {"product_id": self.rice.id, "quantity": 4}, format='json')

        checkout_data = {
            "delivery_type": "delivery",
            "delivery_address": "House No 45, Near Temple, Ward 1",
            "customer_phone": "9800000050",
            "notes": "Please call before arrival"
        }
        res_checkout = self.client.post("/api/v1/orders/cart/checkout/", checkout_data, format='json')
        self.assertEqual(res_checkout.status_code, status.HTTP_201_CREATED)
        self.assertIn('checkout_group_id', res_checkout.data)
        group_id = res_checkout.data['checkout_group_id']
        self.assertTrue(group_id.startswith('ORD-'))

        orders = Order.objects.filter(checkout_group_id=group_id)
        self.assertEqual(orders.count(), 2)

        # Pharmacy order check
        med_order = orders.filter(shop=self.med_shop).first()
        self.assertIsNotNone(med_order)
        self.assertEqual(med_order.total_amount, 50.00) # 25 * 2
        self.assertEqual(med_order.items.count(), 1)
        self.assertEqual(med_order.items.first().product_name, "Paracetamol 650mg")

        # Grocery order check
        groc_order = orders.filter(shop=self.groc_shop).first()
        self.assertIsNotNone(groc_order)
        self.assertEqual(groc_order.total_amount, 200.00) # 50 * 4
        self.assertEqual(groc_order.items.count(), 1)

        # Cart should now be empty
        res_cart = self.client.get("/api/v1/orders/cart/")
        self.assertEqual(res_cart.data['total_items'], 0)

    def test_tamper_proof_pricing(self):
        """Pricing is strictly calculated server-side; client manipulation cannot alter unit_price."""
        self.client.force_authenticate(user=self.customer)
        # Attempt to add with forged client pricing
        add_payload = {
            "product_id": self.paracetamol.id,
            "quantity": 2,
            "unit_price": "1.00",
            "price": "1.00"
        }
        self.client.post("/api/v1/orders/cart/add/", add_payload, format='json')
        res_cart = self.client.get("/api/v1/orders/cart/")
        # Unit price must still be 25.00 (discount_price) and total 50.00
        self.assertEqual(float(res_cart.data['total_amount']), 50.00)

    def test_stock_and_open_status_validated_at_checkout(self):
        """If a shop closes or an item goes out of stock between cart addition and checkout, checkout is blocked."""
        self.client.force_authenticate(user=self.customer)
        self.client.post("/api/v1/orders/cart/add/", {"product_id": self.rice.id, "quantity": 1}, format='json')

        # Shop closes before checkout
        self.groc_shop.is_open = False
        self.groc_shop.save()

        res_checkout = self.client.post("/api/v1/orders/cart/checkout/", {}, format='json')
        self.assertEqual(res_checkout.status_code, status.HTTP_400_BAD_REQUEST)
        # No orders created, cart preserved
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())


class Phase1CoreSecurityAndNotificationTests(TestCase):
    """
    Dedicated tests for Phase 1 Core Security requirements:
    1. Customer B cannot view or modify Customer A's private orders.
    2. Customer B cannot view or modify Customer A's private appointment bookings.
    3. Business Owner B cannot modify Business Owner A's appointments.
    4. Notifications and AuditLogs are dispatched accurately upon order and booking events.
    5. Standardized error payload is returned on validation & permission exceptions.
    """
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Central Area", district="Alappuzha")

        # Business Owner A (Salon)
        self.owner_a = User.objects.create_user(
            phone_number="9847111001",
            password="password123",
            full_name="Salon Owner A",
            role=User.Role.SHOP_OWNER
        )
        self.salon_cat = ShopCategory.objects.create(
            name="Salon & Spa",
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        self.salon_shop = Shop.objects.create(
            owner=self.owner_a,
            name="Elite Spa & Salon",
            category=self.salon_cat,
            area=self.area,
            ward_number=1,
            contact_phone="9847111001",
            is_verified=True,
            is_open=True
        )
        self.facial_service = Product.objects.create(
            shop=self.salon_shop,
            name="Herbal Facial",
            price=800.00,
            is_service=True,
            service_duration_minutes=45,
            is_available=True
        )

        # Business Owner B (Competing Salon / Shop)
        self.owner_b = User.objects.create_user(
            phone_number="9847111002",
            password="password123",
            full_name="Salon Owner B",
            role=User.Role.SHOP_OWNER
        )

        # Customer A
        self.customer_a = User.objects.create_user(
            phone_number="9847222001",
            password="password123",
            full_name="Customer Alice",
            role=User.Role.CITIZEN
        )

        # Customer B (Potential intruder)
        self.customer_b = User.objects.create_user(
            phone_number="9847222002",
            password="password123",
            full_name="Customer Bob",
            role=User.Role.CITIZEN
        )

    def test_customer_b_cannot_view_or_access_customer_a_private_order(self):
        """Customer B cannot view or access Customer A's private order via API (IDOR / BOLA prevention)."""
        order_a = Order.objects.create(
            customer=self.customer_a,
            shop=self.salon_shop,
            status=Order.Status.PENDING,
            total_amount=800.00
        )

        # Customer B attempts to retrieve Customer A's order
        self.client.force_authenticate(user=self.customer_b)
        res = self.client.get(f"/api/v1/orders/orders/{order_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Customer B's order list does not expose Customer A's order
        res_list = self.client.get("/api/v1/orders/orders/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        order_ids = [o['id'] for o in res_list.data.get('results', res_list.data)]
        self.assertNotIn(order_a.id, order_ids)

    def test_customer_b_cannot_view_or_access_customer_a_private_booking(self):
        """Customer B cannot view or access Customer A's appointment booking (privacy guarantee)."""
        booking_a = Booking.objects.create(
            shop=self.salon_shop,
            customer=self.customer_a,
            service=self.facial_service,
            booking_date="2026-11-10",
            time_slot="11:00 AM - 12:00 PM",
            status=Booking.Status.PENDING
        )

        # Customer B attempts to retrieve Customer A's booking
        self.client.force_authenticate(user=self.customer_b)
        res = self.client.get(f"/api/v1/orders/bookings/{booking_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Customer B cannot cancel Customer A's booking
        res_cancel = self.client.post(
            f"/api/v1/orders/bookings/{booking_a.id}/update-status/",
            {"status": Booking.Status.CANCELLED},
            format='json'
        )
        self.assertEqual(res_cancel.status_code, status.HTTP_404_NOT_FOUND)
        booking_a.refresh_from_db()
        self.assertEqual(booking_a.status, Booking.Status.PENDING)

    def test_business_owner_b_cannot_modify_business_owner_a_booking(self):
        """Business Owner B cannot confirm or cancel an appointment booking at Business A's shop."""
        booking_a = Booking.objects.create(
            shop=self.salon_shop,
            customer=self.customer_a,
            service=self.facial_service,
            booking_date="2026-11-10",
            time_slot="02:00 PM - 03:00 PM",
            status=Booking.Status.PENDING
        )

        # Owner B attempts to update booking status
        self.client.force_authenticate(user=self.owner_b)
        res = self.client.post(
            f"/api/v1/orders/bookings/{booking_a.id}/update-status/",
            {"status": Booking.Status.CONFIRMED},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        booking_a.refresh_from_db()
        self.assertEqual(booking_a.status, Booking.Status.PENDING)

    def test_order_creation_triggers_notification_and_audit_log(self):
        """Placing an order sends in-app notification to shop owner and writes AuditLog entry."""
        self.client.force_authenticate(user=self.customer_a)
        data = {
            "shop_id": self.salon_shop.id,
            "items": [{"product_id": self.facial_service.id, "quantity": 1}]
        }
        res = self.client.post("/api/v1/orders/orders/", data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order_id = res.data['id']

        # Verify in-app notification delivered to salon owner
        notif = SocialNotification.objects.filter(
            recipient=self.owner_a,
            notification_type=SocialNotification.Type.ORDER_UPDATE
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn(str(order_id), notif.title)

        # Verify audit log created
        audit = AuditLog.objects.filter(
            target_type='Order',
            target_id=order_id,
            performed_by=self.customer_a
        ).first()
        self.assertIsNotNone(audit)

    def test_booking_creation_and_status_update_triggers_notifications(self):
        """Creating and confirming an appointment dispatches notifications to owner and customer."""
        # 1. Customer creates booking
        self.client.force_authenticate(user=self.customer_a)
        booking_data = {
            "shop": self.salon_shop.id,
            "service": self.facial_service.id,
            "booking_date": "2026-11-12",
            "time_slot": "10:00 AM - 11:00 AM"
        }
        res_create = self.client.post("/api/v1/orders/bookings/", booking_data, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        booking_id = res_create.data['id']

        # Notification to shop owner
        owner_notif = SocialNotification.objects.filter(
            recipient=self.owner_a,
            notification_type=SocialNotification.Type.BOOKING_UPDATE
        ).first()
        self.assertIsNotNone(owner_notif)
        self.assertIn(str(booking_id), owner_notif.title)

        # 2. Shop owner confirms booking
        self.client.force_authenticate(user=self.owner_a)
        res_confirm = self.client.post(
            f"/api/v1/orders/bookings/{booking_id}/update-status/",
            {"status": Booking.Status.CONFIRMED},
            format='json'
        )
        self.assertEqual(res_confirm.status_code, status.HTTP_200_OK)

        # Notification to customer
        cust_notif = SocialNotification.objects.filter(
            recipient=self.customer_a,
            notification_type=SocialNotification.Type.BOOKING_UPDATE
        ).first()
        self.assertIsNotNone(cust_notif)
        self.assertIn(str(booking_id), cust_notif.title)

    def test_standardized_error_envelope_on_exception(self):
        """Exceptions return consistent standardized JSON envelope for mobile and web clients."""
        self.client.force_authenticate(user=self.customer_a)
        # Attempt to order with invalid data to trigger ValidationError
        res = self.client.post("/api/v1/orders/orders/", {}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('success', res.data)
        self.assertFalse(res.data['success'])
        self.assertIn('error', res.data)
        self.assertIn('error_code', res.data)
        self.assertEqual(res.data['error_code'], 'VALIDATION_ERROR')
        self.assertEqual(res.data['status_code'], 400)


