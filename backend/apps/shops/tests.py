from django.test import TestCase, Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Area, AuditLog
from apps.orders.models import Order, OrderItem, Booking
from apps.chat.models import SocialNotification
from .models import ShopCategory, Shop, Product, Review, ShopWorkingHour, RatingCriterion, ReviewCriterionRating

class ShopsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="Central Ward Area", district="Ernakulam")

        self.owner_a = User.objects.create_user(
            phone_number="9800000001",
            password="password123",
            full_name="Shop Owner A",
            role=User.Role.SHOP_OWNER
        )

        self.owner_b = User.objects.create_user(
            phone_number="9800000002",
            password="password123",
            full_name="Attacker Shop Owner B",
            role=User.Role.SHOP_OWNER
        )

        self.admin = User.objects.create_superuser(
            phone_number="9999999999",
            password="adminpassword",
            full_name="Super Admin"
        )

        self.category = ShopCategory.objects.create(
            name="Grocery",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )

        self.shop_a = Shop.objects.create(
            owner=self.owner_a,
            name="Owner A Bakery",
            category=self.category,
            area=self.area,
            ward_number=1,
            address="Near Junction",
            contact_phone="9800000001",
            is_verified=True,
            is_open=True
        )

        self.product_a = Product.objects.create(
            shop=self.shop_a,
            name="Wheat Bread",
            price=45.00,
            unit="1 loaf",
            is_available=True
        )

    def test_unauthorized_user_cannot_delete_another_shop(self):
        """User B cannot delete Shop A (BOLA prevention)."""
        self.client.force_authenticate(user=self.owner_b)
        url = f"/api/v1/shops/shops/{self.shop_a.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Shop.objects.filter(id=self.shop_a.id).exists())

    def test_unauthorized_user_cannot_edit_another_shop(self):
        """User B cannot edit Shop A."""
        self.client.force_authenticate(user=self.owner_b)
        url = f"/api/v1/shops/shops/{self.shop_a.id}/"
        response = self.client.patch(url, {"name": "Hacked Shop"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.shop_a.refresh_from_db()
        self.assertEqual(self.shop_a.name, "Owner A Bakery")

    def test_owner_can_delete_own_shop(self):
        """Owner A can delete their own shop."""
        self.client.force_authenticate(user=self.owner_a)
        url = f"/api/v1/shops/shops/{self.shop_a.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Shop.objects.filter(id=self.shop_a.id).exists())

    def test_unauthorized_user_cannot_delete_product(self):
        """User B cannot delete Product A belonging to Shop A."""
        self.client.force_authenticate(user=self.owner_b)
        url = f"/api/v1/shops/products/{self.product_a.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(id=self.product_a.id).exists())

    def test_unauthorized_user_cannot_add_product_to_another_shop(self):
        """User B cannot add products to Shop A."""
        self.client.force_authenticate(user=self.owner_b)
        url = "/api/v1/shops/products/"
        data = {
            "shop": self.shop_a.id,
            "name": "Unauthorized Cake",
            "price": 200.00,
            "unit": "1 kg"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_toggle_open_restricted_to_owner_or_admin(self):
        """Only the shop owner or admin can toggle open/closed state."""
        self.client.force_authenticate(user=self.owner_b)
        url = f"/api/v1/shops/shops/{self.shop_a.id}/toggle-open/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Owner A can toggle
        self.client.force_authenticate(user=self.owner_a)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.shop_a.refresh_from_db()
        self.assertFalse(self.shop_a.is_open)

    def test_unauthorized_user_cannot_delete_another_review(self):
        """User B cannot delete Review created by User A."""
        review = Review.objects.create(
            shop=self.shop_a,
            user=self.owner_a,
            rating=5,
            comment="Great shop!"
        )
        self.client.force_authenticate(user=self.owner_b)
        url = f"/api/v1/shops/reviews/{review.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Review.objects.filter(id=review.id).exists())


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class WebRoutingAndViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.area = Area.objects.create(name="Central Ward Area", district="Ernakulam")
        self.owner = User.objects.create_user(
            phone_number="9800000010",
            password="password123",
            full_name="Web Shop Owner",
            role=User.Role.SHOP_OWNER
        )
        self.customer = User.objects.create_user(
            phone_number="9800000011",
            password="password123",
            full_name="Web Customer",
            role=User.Role.CITIZEN
        )
        self.category = ShopCategory.objects.create(
            name="Supermarket",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Web Supermarket",
            category=self.category,
            area=self.area,
            ward_number=2,
            address="Main Bazaar",
            contact_phone="9800000010",
            is_verified=True,
            is_open=True
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name="Dairy Milk",
            price=50.00,
            unit="1 pack",
            is_available=True
        )

    def test_url_reverse_resolves_to_html_web_pages(self):
        """Verify URL names resolve to HTML web routes and not DRF API endpoints."""
        self.assertEqual(reverse('home'), '/')
        self.assertEqual(reverse('shop-list'), '/shops/')
        self.assertEqual(reverse('shop-detail', args=[self.shop.id]), f'/shops/{self.shop.id}/')
        self.assertEqual(reverse('order-create', args=[self.shop.id]), f'/shops/{self.shop.id}/order/')
        self.assertEqual(reverse('shop-toggle-open', args=[self.shop.id]), f'/shops/{self.shop.id}/toggle-open/')
        self.assertEqual(reverse('order-update-status', args=[1]), '/dashboard/shop/order/1/status/')

    def test_web_home_page_renders_html(self):
        """Ensure web home page returns 200 and loads index.html template."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_web_shop_list_renders_html(self):
        """Ensure /shops/ returns 200 and loads shop_list.html template."""
        response = self.client.get(reverse('shop-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shops/shop_list.html')
        self.assertContains(response, "Web Supermarket")

    def test_web_shop_detail_renders_html(self):
        """Ensure /shops/<id>/ returns 200 and loads shop_detail.html template."""
        response = self.client.get(reverse('shop-detail', args=[self.shop.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shops/shop_detail.html')
        self.assertContains(response, "Dairy Milk")

    def test_web_order_create_success(self):
        """Test web order creation correctly uses unit_price and redirects to dashboard."""
        self.client.force_login(self.customer)
        post_data = {
            'product_id': self.product.id,
            'quantity': 2,
            'delivery_type': 'pickup',
            'customer_phone': '9800000011',
            'delivery_address': 'Home address'
        }
        response = self.client.post(reverse('order-create', args=[self.shop.id]), post_data)
        self.assertEqual(response.status_code, 302)

        # Verify order in database
        order = Order.objects.filter(customer=self.customer, shop=self.shop).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.product, self.product)
        self.assertEqual(float(item.unit_price), 50.00)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(float(item.subtotal), 100.00)

    def test_web_product_delete_owner_success(self):
        """Shop owner can delete their own product when no order history exists."""
        self.client.force_login(self.owner)
        response = self.client.post(reverse('product-delete', args=[self.product.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_web_product_delete_unauthorized_user_blocked(self):
        """Customer cannot delete shop owner's product (PermissionDenied / 403)."""
        self.client.force_login(self.customer)
        response = self.client.post(reverse('product-delete', args=[self.product.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(id=self.product.id).exists())


class ComprehensiveShopSecurityScenariosTests(TestCase):
    """
    Comprehensive Security Test Suite covering all 15 critical scenarios:
    - BOLA / IDOR protection across web routes and DRF endpoints.
    - Strict server-side ownership validation for create, update, delete, stock toggle.
    - Safe product deletion preserving historical OrderItems.
    - Directory separation of 'My Shop' vs 'Other Shops'.
    """
    def setUp(self):
        self.web_client = Client()
        self.api_client = APIClient()

        self.area = Area.objects.create(name="Central Ward Area", district="Ernakulam")
        self.category = ShopCategory.objects.create(
            name="Community Grocery",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )

        # Shop Owner 1 & Shop 1
        self.owner1 = User.objects.create_user(
            phone_number="9800000021",
            password="password123",
            full_name="Owner One",
            role=User.Role.SHOP_OWNER
        )
        self.shop1 = Shop.objects.create(
            owner=self.owner1,
            name="Owner 1 Supermarket",
            category=self.category,
            area=self.area,
            ward_number=1,
            address="Ward 1 Junction",
            contact_phone="9800000021",
            is_verified=True,
            is_open=True
        )
        self.product1 = Product.objects.create(
            shop=self.shop1,
            name="Organic Rice 5kg",
            price=250.00,
            unit="5 kg",
            is_available=True
        )

        # Shop Owner 2 & Shop 2 (Potential Attacker)
        self.owner2 = User.objects.create_user(
            phone_number="9800000022",
            password="password123",
            full_name="Owner Two",
            role=User.Role.SHOP_OWNER
        )
        self.shop2 = Shop.objects.create(
            owner=self.owner2,
            name="Owner 2 Provisions",
            category=self.category,
            area=self.area,
            ward_number=2,
            address="Ward 2 Market",
            contact_phone="9800000022",
            is_verified=True,
            is_open=True
        )
        self.product2 = Product.objects.create(
            shop=self.shop2,
            name="Tea Powder 250g",
            price=110.00,
            unit="250g",
            is_available=True
        )

        # Regular Citizen / Customer
        self.citizen = User.objects.create_user(
            phone_number="9800000023",
            password="password123",
            full_name="Citizen Buyer",
            role=User.Role.CITIZEN
        )

        # Super Admin
        self.admin = User.objects.create_superuser(
            phone_number="9999999998",
            password="adminpassword",
            full_name="Portal Administrator"
        )

    # --------------------------------------------------------------------------
    # Scenario 1: Shop owner can view and edit their own products
    # --------------------------------------------------------------------------
    def test_scenario_01_owner_can_view_and_edit_own_product(self):
        self.web_client.force_login(self.owner1)
        edit_url = reverse('product-edit', args=[self.product1.id])
        payload = {
            'name': 'Organic Rice 5kg Premium',
            'price': '275.00',
            'discount_price': '260.00',
            'unit': '5 kg bag',
            'description': 'High quality organic rice',
            'is_available': 'on',
        }
        response = self.web_client.post(edit_url, payload)
        self.assertEqual(response.status_code, 302)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, 'Organic Rice 5kg Premium')
        self.assertEqual(float(self.product1.price), 275.00)
        self.assertEqual(float(self.product1.discount_price), 260.00)

    # --------------------------------------------------------------------------
    # Scenario 2: Shop owner CANNOT edit another shop's product (HTML view)
    # --------------------------------------------------------------------------
    def test_scenario_02_owner_cannot_edit_another_shop_product_html(self):
        self.web_client.force_login(self.owner2)
        edit_url = reverse('product-edit', args=[self.product1.id])
        payload = {
            'name': 'Hacked Rice',
            'price': '1.00',
        }
        response = self.web_client.post(edit_url, payload)
        self.assertEqual(response.status_code, 403)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, 'Organic Rice 5kg')
        self.assertEqual(float(self.product1.price), 250.00)

    # --------------------------------------------------------------------------
    # Scenario 3: Shop owner CANNOT edit another shop's product (DRF API)
    # --------------------------------------------------------------------------
    def test_scenario_03_owner_cannot_edit_another_shop_product_api(self):
        self.api_client.force_authenticate(user=self.owner2)
        api_url = f"/api/v1/shops/products/{self.product1.id}/"
        payload = {
            'name': 'API Hacked Rice',
            'price': '5.00'
        }
        response = self.api_client.patch(api_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, 'Organic Rice 5kg')

    # --------------------------------------------------------------------------
    # Scenario 4: Shop owner CANNOT delete another shop's product (HTML view)
    # --------------------------------------------------------------------------
    def test_scenario_04_owner_cannot_delete_another_shop_product_html(self):
        self.web_client.force_login(self.owner2)
        delete_url = reverse('product-delete', args=[self.product1.id])
        response = self.web_client.post(delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(id=self.product1.id).exists())

    # --------------------------------------------------------------------------
    # Scenario 5: Shop owner CANNOT delete another shop's product (DRF API)
    # --------------------------------------------------------------------------
    def test_scenario_05_owner_cannot_delete_another_shop_product_api(self):
        self.api_client.force_authenticate(user=self.owner2)
        api_url = f"/api/v1/shops/products/{self.product1.id}/"
        response = self.api_client.delete(api_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(id=self.product1.id).exists())

    # --------------------------------------------------------------------------
    # Scenario 6: Shop owner CANNOT toggle stock of another shop's product (HTML view)
    # --------------------------------------------------------------------------
    def test_scenario_06_owner_cannot_toggle_stock_another_shop_product(self):
        self.web_client.force_login(self.owner2)
        toggle_url = reverse('product-toggle-stock', args=[self.product1.id])
        response = self.web_client.post(toggle_url)
        self.assertEqual(response.status_code, 403)
        self.product1.refresh_from_db()
        self.assertTrue(self.product1.is_available)

    # --------------------------------------------------------------------------
    # Scenario 7: Shop owner CANNOT add a product to another shop (HTML view)
    # --------------------------------------------------------------------------
    def test_scenario_07_owner_cannot_add_product_to_another_shop_html(self):
        self.web_client.force_login(self.owner2)
        create_url = reverse('product-create', args=[self.shop1.id])
        payload = {
            'name': 'Unauthorized Bread',
            'price': '40.00',
            'unit': '1 loaf'
        }
        response = self.web_client.post(create_url, payload)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Product.objects.filter(name='Unauthorized Bread').exists())

    # --------------------------------------------------------------------------
    # Scenario 8: Shop owner CANNOT add a product to another shop (DRF API)
    # --------------------------------------------------------------------------
    def test_scenario_08_owner_cannot_add_product_to_another_shop_api(self):
        self.api_client.force_authenticate(user=self.owner2)
        api_url = "/api/v1/shops/products/"
        payload = {
            'shop': self.shop1.id,
            'name': 'Unauthorized API Cake',
            'price': '150.00',
            'unit': '1 kg'
        }
        response = self.api_client.post(api_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Product.objects.filter(name='Unauthorized API Cake').exists())

    # --------------------------------------------------------------------------
    # Scenario 9: Non-owner / citizen CANNOT edit, delete, or toggle any product
    # --------------------------------------------------------------------------
    def test_scenario_09_citizen_cannot_modify_products(self):
        self.web_client.force_login(self.citizen)

        # Try edit
        edit_resp = self.web_client.post(reverse('product-edit', args=[self.product1.id]), {'name': 'Civ', 'price': '10'})
        self.assertEqual(edit_resp.status_code, 403)

        # Try toggle stock
        toggle_resp = self.web_client.post(reverse('product-toggle-stock', args=[self.product1.id]))
        self.assertEqual(toggle_resp.status_code, 403)

        # Try delete
        del_resp = self.web_client.post(reverse('product-delete', args=[self.product1.id]))
        self.assertEqual(del_resp.status_code, 403)

        # Try add product
        add_resp = self.web_client.post(reverse('product-create', args=[self.shop1.id]), {'name': 'Civ Item', 'price': '10'})
        self.assertEqual(add_resp.status_code, 403)

    # --------------------------------------------------------------------------
    # Scenario 10: Anonymous / unauthenticated user redirected on modification
    # --------------------------------------------------------------------------
    def test_scenario_10_anonymous_user_redirected_to_login(self):
        # Product edit
        resp_edit = self.web_client.post(reverse('product-edit', args=[self.product1.id]))
        self.assertEqual(resp_edit.status_code, 302)
        self.assertIn('/auth/login/', resp_edit.url if hasattr(resp_edit, 'url') else resp_edit.headers.get('Location'))

        # Product toggle stock
        resp_toggle = self.web_client.post(reverse('product-toggle-stock', args=[self.product1.id]))
        self.assertEqual(resp_toggle.status_code, 302)

        # Product delete
        resp_del = self.web_client.post(reverse('product-delete', args=[self.product1.id]))
        self.assertEqual(resp_del.status_code, 302)

        # Product create
        resp_create = self.web_client.post(reverse('product-create', args=[self.shop1.id]))
        self.assertEqual(resp_create.status_code, 302)

    # --------------------------------------------------------------------------
    # Scenario 11: Product deletion with order history preserves OrderItem (Safe Deletion)
    # --------------------------------------------------------------------------
    def test_scenario_11_safe_deletion_with_order_history(self):
        order = Order.objects.create(
            customer=self.citizen,
            shop=self.shop1,
            status=Order.Status.COMPLETED,
            total_amount=250.00
        )
        order_item = OrderItem.objects.create(
            order=order,
            product=self.product1,
            product_name=self.product1.name,
            quantity=1,
            unit_price=self.product1.price,
            subtotal=250.00
        )

        # Owner 1 attempts to delete product1
        self.web_client.force_login(self.owner1)
        response = self.web_client.post(reverse('product-delete', args=[self.product1.id]))
        self.assertEqual(response.status_code, 302)

        # Product row still exists to preserve referential integrity, but is archived (is_available=False)
        self.product1.refresh_from_db()
        self.assertFalse(self.product1.is_available)
        self.assertTrue(Product.objects.filter(id=self.product1.id).exists())

        # Historical order item remains intact
        order_item.refresh_from_db()
        self.assertEqual(order_item.product_id, self.product1.id)
        self.assertEqual(order_item.product_name, "Organic Rice 5kg")

    # --------------------------------------------------------------------------
    # Scenario 12: Product deletion without order history deletes successfully
    # --------------------------------------------------------------------------
    def test_scenario_12_safe_deletion_without_order_history(self):
        new_prod = Product.objects.create(
            shop=self.shop1,
            name="Temporary Vegetable",
            price=30.00,
            unit="1 kg"
        )
        self.web_client.force_login(self.owner1)
        response = self.web_client.post(reverse('product-delete', args=[new_prod.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(id=new_prod.id).exists())

    # --------------------------------------------------------------------------
    # Scenario 13: "My Shop" dashboard shows only the authenticated owner's shop data
    # --------------------------------------------------------------------------
    def test_scenario_13_dashboard_shows_only_owner_shop_data(self):
        self.web_client.force_login(self.owner1)
        response = self.web_client.get(reverse('shop-dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.shop1.name)
        self.assertContains(response, self.product1.name)
        self.assertNotContains(response, self.shop2.name)
        self.assertNotContains(response, self.product2.name)

    # --------------------------------------------------------------------------
    # Scenario 14: Public shop list properly separates or excludes owner's shop when filtered
    # --------------------------------------------------------------------------
    def test_scenario_14_public_shop_list_separates_my_shop_and_other_shops(self):
        self.web_client.force_login(self.owner1)

        # Normal view lists shops with "My Shop" badge on owner1's shop
        resp_all = self.web_client.get(reverse('shop-list'))
        self.assertEqual(resp_all.status_code, 200)
        self.assertContains(resp_all, self.shop1.name)
        self.assertContains(resp_all, self.shop2.name)
        self.assertContains(resp_all, "എന്റെ കട (My Shop)")

        # Filtered to 'other' shops excludes owner1's shop
        resp_other = self.web_client.get(reverse('shop-list') + '?scope=other')
        self.assertEqual(resp_other.status_code, 200)
        self.assertNotContains(resp_other, self.shop1.name)
        self.assertContains(resp_other, self.shop2.name)

    # --------------------------------------------------------------------------
    # Scenario 15: Cross-shop product reassociation attempt via API rejected
    # --------------------------------------------------------------------------
    def test_scenario_15_cross_shop_product_reassociation_rejected_api(self):
        self.api_client.force_authenticate(user=self.owner2)
        api_url = f"/api/v1/shops/products/{self.product2.id}/"
        # Owner 2 tries to reassign their product2 to shop1
        payload = {
            'shop': self.shop1.id,
            'name': 'Hijacked to Shop1'
        }
        response = self.api_client.patch(api_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.shop_id, self.shop2.id)

    # --------------------------------------------------------------------------
    # Scenario 16: Owner viewing another shop detail page: management controls HIDDEN
    # --------------------------------------------------------------------------
    def test_scenario_16_other_shop_detail_page_hides_management_controls(self):
        """
        When Owner 1 logs in and views Shop 2 (/shops/<shop2.id>/),
        management controls (stock toggle, delete) and owner banner must NOT be visible.
        """
        self.web_client.force_login(self.owner1)
        response = self.web_client.get(reverse('shop-detail', args=[self.shop2.id]))
        self.assertEqual(response.status_code, 200)

        # Context booleans must reflect lack of ownership
        self.assertFalse(response.context['is_shop_owner'])
        self.assertFalse(response.context['can_manage_shop'])

        # Buttons must NOT appear in HTML
        self.assertNotContains(response, '🔴 സ്റ്റോക്ക് മാറ്റുക')
        self.assertNotContains(response, '🗑️</span>\n              <span>ഡിലീറ്റ്')
        self.assertNotContains(response, reverse('product-toggle-stock', args=[self.product2.id]))
        self.assertNotContains(response, reverse('product-delete', args=[self.product2.id]))
        self.assertNotContains(response, 'നിങ്ങൾ ഈ കടയുടെ ഉടമസ്ഥനാണ്')

    # --------------------------------------------------------------------------
    # Scenario 17: Owner viewing OWN shop detail page: management controls VISIBLE
    # --------------------------------------------------------------------------
    def test_scenario_17_own_shop_detail_page_shows_management_controls(self):
        """
        When Owner 1 logs in and views their own Shop 1 (/shops/<shop1.id>/),
        management controls (stock toggle, delete) and owner banner MUST be visible.
        """
        self.web_client.force_login(self.owner1)
        response = self.web_client.get(reverse('shop-detail', args=[self.shop1.id]))
        self.assertEqual(response.status_code, 200)

        # Context booleans must confirm ownership
        self.assertTrue(response.context['is_shop_owner'])
        self.assertTrue(response.context['can_manage_shop'])

        # Buttons must appear in HTML
        self.assertContains(response, '🔴 സ്റ്റോക്ക് മാറ്റുക')
        self.assertContains(response, reverse('product-toggle-stock', args=[self.product1.id]))
        self.assertContains(response, reverse('product-delete', args=[self.product1.id]))
        self.assertContains(response, 'നിങ്ങൾ ഈ കടയുടെ ഉടമസ്ഥനാണ്')

    # --------------------------------------------------------------------------
    # Scenario 18: Direct POST request with another shop's product ID returns 403 Forbidden
    # --------------------------------------------------------------------------
    def test_scenario_18_direct_post_tampering_blocked_by_backend_403(self):
        """
        Even if an attacker sends a direct POST with another shop's product ID,
        the backend must block it with HTTP 403 Forbidden.
        """
        self.web_client.force_login(self.owner1)

        # Attempt to toggle stock of Product 2 (belonging to Shop 2)
        toggle_response = self.web_client.post(reverse('product-toggle-stock', args=[self.product2.id]))
        self.assertEqual(toggle_response.status_code, 403)

        # Attempt to delete Product 2 (belonging to Shop 2)
        delete_response = self.web_client.post(reverse('product-delete', args=[self.product2.id]))
        self.assertEqual(delete_response.status_code, 403)

        # Attempt to edit Product 2 (belonging to Shop 2)
        edit_response = self.web_client.post(reverse('product-edit', args=[self.product2.id]), {
            'name': 'Hacked by Owner 1',
            'price': '999.00'
        })
        self.assertEqual(edit_response.status_code, 403)

    # --------------------------------------------------------------------------
    # Scenario 19: Beauty Parlour Business Type, Service Management & Appointment Booking
    # --------------------------------------------------------------------------
    def test_scenario_19_beauty_parlour_service_and_appointment_booking(self):
        """
        Verify that Beauty Parlours operate with services (with duration in minutes)
        and support appointment booking without requiring physical product stock.
        """
        # Create Beauty Parlour category and shop
        parlour_cat = ShopCategory.objects.create(
            name="Beauty Parlour & Salon",
            business_type=ShopCategory.BusinessType.BEAUTY_PARLOUR,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        parlour_owner = User.objects.create_user(
            phone_number="9800000030",
            password="password123",
            full_name="Lakshmi Parlour Owner",
            role=User.Role.SHOP_OWNER
        )
        parlour_shop = Shop.objects.create(
            owner=parlour_owner,
            name="Lakshmi Beauty Parlour",
            category=parlour_cat,
            area=self.area,
            ward_number=3,
            address="Near Temple Road",
            contact_phone="9800000030",
            is_verified=True,
            is_open=True
        )

        # Parlour owner creates a service with duration
        self.web_client.force_login(parlour_owner)
        add_service_url = reverse('product-create', args=[parlour_shop.id])
        service_payload = {
            'name': 'Gold Facial & Cleanup',
            'price': '1200.00',
            'duration_minutes': '60',
            'description': 'Rejuvenating herbal gold facial treatment',
            'is_available': 'on',
        }
        res = self.web_client.post(add_service_url, service_payload)
        self.assertEqual(res.status_code, 302)

        service = Product.objects.get(shop=parlour_shop, name='Gold Facial & Cleanup')
        self.assertEqual(service.service_duration_minutes, 60)
        self.assertTrue(service.is_service)
        self.assertIn("60", service.duration_display)

        # Citizen views parlour page - should show service duration and appointment booking action
        self.web_client.force_login(self.citizen)
        detail_res = self.web_client.get(reverse('shop-detail', args=[parlour_shop.id]))
        self.assertEqual(detail_res.status_code, 200)
        self.assertTrue(detail_res.context['is_service_based'])
        self.assertTrue(detail_res.context['is_beauty_parlour'])
        self.assertContains(detail_res, 'Gold Facial & Cleanup')
        self.assertContains(detail_res, 'അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യാം')

        # Citizen requests an appointment booking
        book_url = reverse('booking-create', args=[parlour_shop.id])
        booking_data = {
            'service_id': service.id,
            'booking_date': '2026-11-05',
            'time_slot': '10:00 AM - 11:00 AM',
            'number_of_people': 1,
            'customer_phone': '9800000023',
            'special_notes': 'Bridal consultation required'
        }
        book_res = self.web_client.post(book_url, booking_data)
        self.assertEqual(book_res.status_code, 302)

        booking = Booking.objects.filter(shop=parlour_shop, customer=self.citizen).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.service_id, service.id)
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.time_slot, '10:00 AM - 11:00 AM')

        # Parlour Owner sees the booking in shop dashboard and confirms it
        self.web_client.force_login(parlour_owner)
        dash_res = self.web_client.get(reverse('shop-dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'അപ്പോയിന്റ്മെന്റുകൾ / ബുക്കിംഗുകൾ')
        self.assertContains(dash_res, 'Gold Facial & Cleanup')

        # Owner updates booking status to confirmed
        status_url = reverse('booking-update-status', args=[booking.id])
        status_res = self.web_client.post(status_url, {'status': Booking.Status.CONFIRMED})
        self.assertEqual(status_res.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

        # Another owner (Owner 2) attempts to update/tamper with this parlour booking -> 403 Forbidden
        self.web_client.force_login(self.owner2)
        tamper_res = self.web_client.post(status_url, {'status': Booking.Status.CANCELLED})
        self.assertEqual(tamper_res.status_code, 403)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

        # Citizen attempts to cancel booking AFTER shop owner has confirmed it:
        # Backend blocks cancellation because it is already confirmed/approved!
        self.web_client.force_login(self.citizen)
        cancel_url = reverse('booking-cancel', args=[booking.id])
        cancel_after_approval_res = self.web_client.post(cancel_url)
        # Booking must remain CONFIRMED
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

        # Also verify UI: Citizen dashboard shows '✓ സ്ഥാപനം സ്ഥിരീകരിച്ചു' and NO cancel button
        user_dash_res = self.web_client.get(reverse('user-dashboard'))
        self.assertEqual(user_dash_res.status_code, 200)
        self.assertContains(user_dash_res, 'സ്ഥാപനം സ്ഥിരീകരിച്ചു')
        self.assertNotContains(user_dash_res, f"action=\"{cancel_url}\"")

    # --------------------------------------------------------------------------
    # Scenario 20: Shop owner viewing own shop: Cart, Buy Now & Booking HIDDEN
    # --------------------------------------------------------------------------
    def test_scenario_20_own_shop_detail_hides_cart_and_order_and_booking_controls(self):
        """
        Verify that when a shop owner views their own shop's detail page:
        1. 'Add to Cart' (കാർട്ടിലേക്ക് ചേർക്കുക) and 'Buy Now' (ഇപ്പോൾ തന്നെ വാങ്ങാം) are HIDDEN.
        2. Own shop indicator (നിങ്ങളുടെ സ്വന്തം സ്ഥാപനം) is displayed instead.
        3. Direct POST to cart-add or order-create for own shop is blocked by backend.
        4. When another user (citizen) views the shop, buying controls are fully accessible.
        """
        # 1. Owner 1 views their own Shop 1
        self.web_client.force_login(self.owner1)
        res_own = self.web_client.get(reverse('shop-detail', args=[self.shop1.id]))
        self.assertEqual(res_own.status_code, 200)
        self.assertTrue(res_own.context['can_manage_shop'])

        # Ordering / Cart controls must NOT be visible to the shop's owner
        self.assertNotContains(res_own, 'കാർട്ടിലേക്ക് ചേർക്കുക')
        self.assertNotContains(res_own, 'ഇപ്പോൾ തന്നെ വാങ്ങാം')
        self.assertNotContains(res_own, reverse('cart-add', args=[self.product1.id]))
        self.assertContains(res_own, 'നിങ്ങളുടെ സ്വന്തം സ്ഥാപനം')

        # 2. Owner 1 attempts a direct POST to cart-add for own product -> Blocked!
        cart_add_res = self.web_client.post(reverse('cart-add', args=[self.product1.id]), {'quantity': 1})
        self.assertEqual(cart_add_res.status_code, 302)
        from apps.orders.models import Cart
        cart = Cart.objects.filter(customer=self.owner1).first()
        if cart:
            self.assertFalse(cart.items.filter(product=self.product1).exists())

        # 3. Owner 1 attempts a direct POST to order-create for own shop -> Blocked!
        order_create_res = self.web_client.post(reverse('order-create', args=[self.shop1.id]), {
            'product_id': self.product1.id,
            'quantity': 1,
            'customer_phone': '9800000001'
        })
        self.assertEqual(order_create_res.status_code, 302)
        from apps.orders.models import Order
        self.assertFalse(Order.objects.filter(customer=self.owner1, shop=self.shop1).exists())

        # 4. Citizen views Shop 1 -> Buying / Cart controls MUST be visible and functional
        self.web_client.force_login(self.citizen)
        res_cust = self.web_client.get(reverse('shop-detail', args=[self.shop1.id]))
        self.assertEqual(res_cust.status_code, 200)
        self.assertFalse(res_cust.context['can_manage_shop'])
        self.assertContains(res_cust, 'കാർട്ടിലേക്ക് ചേർക്കുക')
        self.assertContains(res_cust, 'ഇപ്പോൾ തന്നെ വാങ്ങാം')
        self.assertNotContains(res_cust, 'നിങ്ങളുടെ സ്വന്തം സ്ഥാപനം')


class NearbyShopsAndLocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.web_client = Client()

        self.area = Area.objects.create(name="Kochi Central", district="Ernakulam")
        self.cat_grocery = ShopCategory.objects.create(name="Grocery", interaction_mode=ShopCategory.InteractionMode.ORDER)
        self.cat_salon = ShopCategory.objects.create(name="Salon & Spa", interaction_mode=ShopCategory.InteractionMode.BOOKING)

        self.owner_a = User.objects.create_user(
            phone_number="9847111111",
            password="password123",
            full_name="Shop Owner A",
            role=User.Role.SHOP_OWNER
        )
        self.owner_b = User.objects.create_user(
            phone_number="9847222222",
            password="password123",
            full_name="Shop Owner B",
            role=User.Role.SHOP_OWNER
        )
        self.citizen = User.objects.create_user(
            phone_number="9847333333",
            password="password123",
            full_name="Normal Citizen",
            role=User.Role.CITIZEN
        )

        # Shop 1: Near (2 km away, Grocery)
        self.shop_near = Shop.objects.create(
            owner=self.owner_a,
            name="Near Grocery Shop",
            category=self.cat_grocery,
            area=self.area,
            ward_number=1,
            address="Near Junction",
            contact_phone="9847111111",
            latitude=10.0200,
            longitude=76.3500,
            is_verified=True,
            is_open=True
        )

        # Shop 2: Far (15 km away, Grocery)
        self.shop_far = Shop.objects.create(
            owner=self.owner_b,
            name="Far Supermarket",
            category=self.cat_grocery,
            area=self.area,
            ward_number=2,
            address="Far Junction",
            contact_phone="9847222222",
            latitude=10.1200,
            longitude=76.4200,
            is_verified=True,
            is_open=True
        )

        # Shop 3: Near (3 km away, Salon)
        self.shop_salon = Shop.objects.create(
            owner=self.owner_b,
            name="Near Beauty Parlour",
            category=self.cat_salon,
            area=self.area,
            ward_number=1,
            address="Salon Corner",
            contact_phone="9847222223",
            latitude=10.0300,
            longitude=76.3600,
            is_verified=True,
            is_open=True
        )

        # Shop 4: No GPS coordinates
        self.shop_no_gps = Shop.objects.create(
            owner=self.owner_a,
            name="No GPS Store",
            category=self.cat_grocery,
            area=self.area,
            ward_number=1,
            address="Unknown Street",
            contact_phone="9847111112",
            latitude=None,
            longitude=None,
            is_verified=True,
            is_open=True
        )

        # User location center: (10.0100, 76.3400)
        self.user_lat = 10.0100
        self.user_lng = 76.3400

    def test_nearby_shops_sorted_by_distance(self):
        """Returns verified active shops within radius sorted ascending by distance."""
        url = f'/api/v1/shops/nearby/?lat={self.user_lat}&lng={self.user_lng}&radius=20'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        shops = res.data['shops']
        shop_ids = [s['id'] for s in shops]

        # Near shops must come before far shops
        self.assertIn(self.shop_near.id, shop_ids)
        self.assertIn(self.shop_far.id, shop_ids)
        self.assertNotIn(self.shop_no_gps.id, shop_ids)  # Excludes shops without coordinates

        # Distance ordering check
        distances = [s['distance_km'] for s in shops]
        self.assertEqual(distances, sorted(distances))

    def test_nearby_shops_category_filter(self):
        """Filters shops by category ID."""
        url = f'/api/v1/shops/nearby/?lat={self.user_lat}&lng={self.user_lng}&radius=20&category={self.cat_salon.id}'
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        shops = res.data['shops']
        shop_ids = [s['id'] for s in shops]
        self.assertIn(self.shop_salon.id, shop_ids)
        self.assertNotIn(self.shop_near.id, shop_ids)

    def test_nearby_shops_without_coordinates_returns_all_verified_shops(self):
        """When GPS coordinates are omitted or denied, returns all verified shops with coordinates gracefully."""
        res = self.client.get('/api/v1/shops/nearby/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('shops', res.data)
        self.assertFalse(res.data['has_user_location'])
        self.assertIsNone(res.data['user_lat'])
        self.assertIsNone(res.data['user_lng'])

        shop_ids = [s['id'] for s in res.data['shops']]
        self.assertIn(self.shop_near.id, shop_ids)
        self.assertIn(self.shop_far.id, shop_ids)
        self.assertNotIn(self.shop_no_gps.id, shop_ids)

    def test_nearby_shops_directions_url_destination(self):
        """Verifies Get Directions URL contains exact shop destination coordinates."""
        res = self.client.get('/api/v1/shops/nearby/')
        self.assertEqual(res.status_code, 200)
        near_item = next(s for s in res.data['shops'] if s['id'] == self.shop_near.id)
        expected_dest = f"destination={self.shop_near.latitude},{self.shop_near.longitude}"
        self.assertIn(expected_dest, near_item['directions_url'])

    def test_nearby_shops_web_page_renders_with_map_container(self):
        """Verifies the /shops/nearby/ HTML view renders with map container and Leaflet assets."""
        res = self.client.get('/shops/nearby/')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode('utf-8')
        self.assertIn('id="shopsMap"', content)
        self.assertIn('leaflet.css', content)
        self.assertIn('leaflet.js', content)
        self.assertIn('defaultCenterLat', content)

    def test_shop_location_update_requires_owner(self):
        """Only the verified shop owner can update the shop coordinates."""
        # Non-owner citizen gets 403 Forbidden
        self.client.force_authenticate(user=self.citizen)
        url = f'/api/v1/shops/{self.shop_near.id}/location/'
        res = self.client.post(url, {"latitude": 10.0500, "longitude": 76.3800}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Owner B gets 403 Forbidden on Owner A's shop
        self.client.force_authenticate(user=self.owner_b)
        res = self.client.post(url, {"latitude": 10.0500, "longitude": 76.3800}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Owner A can update location successfully
        self.client.force_authenticate(user=self.owner_a)
        res = self.client.post(url, {"latitude": 10.0500, "longitude": 76.3800}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.shop_near.refresh_from_db()
        self.assertEqual(self.shop_near.latitude, 10.0500)
        self.assertEqual(self.shop_near.longitude, 76.3800)

    def test_shop_location_update_invalid_coordinates(self):
        """Invalid coordinate numbers return 400 Bad Request."""
        self.client.force_authenticate(user=self.owner_a)
        url = f'/api/v1/shops/{self.shop_near.id}/location/'
        res = self.client.post(url, {"latitude": 95.0, "longitude": 76.0}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_shop_detail_has_directions_url_and_gps_context(self):
        """Shop detail page renders directions_url when coordinates exist."""
        res = self.web_client.get(reverse('shop-detail', args=[self.shop_near.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['has_gps_location'])
        self.assertIn('google.com/maps/dir/', res.context['directions_url'])

    def test_web_shop_location_edit_get(self):
        """Shop location edit page provides shop, current_lat, current_lng, and has_location in context."""
        self.web_client.force_login(self.owner_a)
        res = self.web_client.get(reverse('shop-location-edit', args=[self.shop_near.id]))
        self.assertEqual(res.status_code, 200)
        self.assertIn('current_lat', res.context)
        self.assertIn('current_lng', res.context)
        self.assertIn('has_location', res.context)
        self.assertTrue(res.context['has_location'])
        self.assertEqual(float(res.context['current_lat']), float(self.shop_near.latitude))
        self.assertEqual(float(res.context['current_lng']), float(self.shop_near.longitude))
        self.assertContains(res, 'id="shopLocationMap"')

    def test_web_shop_location_edit_post_update(self):
        """Shop owner can update location coordinates via web view."""
        self.web_client.force_login(self.owner_a)
        res = self.web_client.post(reverse('shop-location-edit', args=[self.shop_near.id]), {
            'latitude': '10.512345',
            'longitude': '76.212345',
            'address': 'Updated Shop Address'
        })
        self.assertEqual(res.status_code, 302)
        self.shop_near.refresh_from_db()
        self.assertEqual(float(self.shop_near.latitude), 10.512345)
        self.assertEqual(float(self.shop_near.longitude), 76.212345)

    def test_web_shop_location_edit_clear_location(self):
        """Shop owner can clear/remove GPS location."""
        self.web_client.force_login(self.owner_a)
        res = self.web_client.post(reverse('shop-location-edit', args=[self.shop_near.id]), {
            'clear_location': 'true'
        })
        self.assertEqual(res.status_code, 302)
        self.shop_near.refresh_from_db()
        self.assertIsNone(self.shop_near.latitude)
        self.assertIsNone(self.shop_near.longitude)

    def test_web_shop_location_edit_permission_denied_for_other_owner(self):
        """Non-owner user cannot access or edit shop location."""
        self.web_client.force_login(self.owner_b)
        res = self.web_client.get(reverse('shop-location-edit', args=[self.shop_near.id]))
        self.assertEqual(res.status_code, 403)

    # --------------------------------------------------------------------------
    # Phase 1 Core Security: Object-level authorization & Audit Logging
    # --------------------------------------------------------------------------
    def test_owner_b_cannot_toggle_stock_of_owner_a_product_api(self):
        """Owner B cannot toggle stock of a product belonging to Owner A via API (BOLA prevention)."""
        product = Product.objects.create(
            shop=self.shop_near,  # Owned by owner_a
            name="Fresh Milk",
            price=30.00,
            unit="500 ml",
            is_available=True
        )
        url = f"/api/v1/shops/products/{product.id}/toggle-stock/"

        # Owner B tries to toggle Owner A's product stock
        self.client.force_authenticate(user=self.owner_b)
        res = self.client.post(url, {"is_available": False}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        product.refresh_from_db()
        self.assertTrue(product.is_available)

        # Owner A successfully toggles stock and generates AuditLog entry
        self.client.force_authenticate(user=self.owner_a)
        res_ok = self.client.post(url, {"is_available": False}, format='json')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertFalse(product.is_available)

        audit = AuditLog.objects.filter(
            target_type='Product',
            target_id=product.id,
            action=AuditLog.Action.PRODUCT_STOCK_TOGGLE
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.performed_by, self.owner_a)

    def test_owner_b_cannot_edit_or_delete_owner_a_product_api(self):
        """Owner B cannot modify or delete product belonging to Owner A via API."""
        product = Product.objects.create(
            shop=self.shop_near,  # Owned by owner_a
            name="Organic Honey",
            price=250.00,
            unit="500 g",
            is_available=True
        )
        url = f"/api/v1/shops/products/{product.id}/"

        # Owner B attempts PATCH
        self.client.force_authenticate(user=self.owner_b)
        patch_res = self.client.patch(url, {"name": "Hacked Honey", "price": 10.00}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)
        product.refresh_from_db()
        self.assertEqual(product.name, "Organic Honey")

        # Owner B attempts DELETE
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(id=product.id).exists())

        # Owner A can delete and creates audit log
        self.client.force_authenticate(user=self.owner_a)
        del_ok = self.client.delete(url)
        self.assertEqual(del_ok.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=product.id).exists())

        audit = AuditLog.objects.filter(
            target_type='Product',
            target_id=product.id,
            action=AuditLog.Action.PRODUCT_DELETE
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.performed_by, self.owner_a)

    def test_product_with_order_history_is_soft_deleted_not_hard_deleted(self):
        """Deleting a product that has historical OrderItems soft-deletes it (marks is_available=False)."""
        product = Product.objects.create(
            shop=self.shop_near,
            name="Special Ghee",
            price=300.00,
            unit="500 ml",
            is_available=True
        )
        order = Order.objects.create(
            customer=self.citizen,
            shop=self.shop_near,
            status=Order.Status.COMPLETED,
            total_amount=300.00
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price=300.00,
            subtotal=300.00
        )

        self.client.force_authenticate(user=self.owner_a)
        url = f"/api/v1/shops/products/{product.id}/"
        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)

        # Product still exists in DB but is unavailable (soft-deleted)
        product.refresh_from_db()
        self.assertFalse(product.is_available)
        self.assertTrue(Product.objects.filter(id=product.id).exists())

        audit = AuditLog.objects.filter(
            target_type='Product',
            target_id=product.id,
            action=AuditLog.Action.PRODUCT_DELETE
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("Soft-deleted", audit.reason)


class Phase3BusinessCategoriesIndependentTests(TestCase):
    """
    Independent validation for all 6 business categories under Phase 3:
    1. General Shops: Products, Stock, Prices, Cart, Orders.
    2. Medical Shops: Prescription drug requirements, dosage/expiry info, service requests for pharmacist check.
    3. Beauty Parlours: Service listings, duration in minutes, appointment booking, slot confirmation.
    4. Restaurants: Menus, delivery radius, table booking / food ordering.
    5. Repair Shops: Custom service requests, diagnostic descriptions, quote responses.
    6. Other Service Providers: Hourly/unit pricing, availability, and appointments.
    """
    def setUp(self):
        self.client = APIClient()
        self.web_client = Client()
        self.area = Area.objects.create(name="Business Central Ward", district="Ernakulam")

        # Citizen Customer
        self.citizen = User.objects.create_user(
            phone_number="9847555001",
            password="password123",
            full_name="Consumer Citizen",
            role=User.Role.CITIZEN
        )

    def test_general_shop_flow(self):
        """General Store: Products, stock toggle, prices, and direct ordering."""
        owner = User.objects.create_user(
            phone_number="9847555002", password="password123", full_name="General Merchant", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="General Supermarket",
            business_type=ShopCategory.BusinessType.GENERAL,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        shop = Shop.objects.create(
            owner=owner, name="Village Super Bazaar", category=cat, area=self.area, ward_number=1,
            contact_phone="9847555002", is_verified=True, is_open=True
        )
        product = Product.objects.create(
            shop=shop, name="Washing Soap Bar", price=40.00, discount_price=35.00, unit="1 pack", is_available=True
        )

        self.assertTrue(shop.is_product_based)
        self.assertFalse(shop.is_service_based)

        # Citizen places order
        self.client.force_authenticate(user=self.citizen)
        order_res = self.client.post("/api/v1/orders/orders/", {
            "shop_id": shop.id,
            "delivery_type": "pickup",
            "items": [{"product_id": product.id, "quantity": 3}]
        }, format='json')
        self.assertEqual(order_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(order_res.data['total_amount']), 105.00) # 35 * 3

    def test_medical_shop_flow(self):
        """Medical Shop: Prescription drug warnings and pharmacist prescription requests."""
        owner = User.objects.create_user(
            phone_number="9847555003", password="password123", full_name="Licensed Pharmacist", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="Medical & Pharmacy",
            business_type=ShopCategory.BusinessType.MEDICAL,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        shop = Shop.objects.create(
            owner=owner, name="Care Community Pharmacy", category=cat, area=self.area, ward_number=1,
            contact_phone="9847555003", is_verified=True, is_open=True
        )
        rx_drug = Product.objects.create(
            shop=shop, name="Amoxicillin 500mg", price=120.00, requires_prescription=True, expiry_info="Exp 11/2027", is_available=True
        )

        self.assertTrue(shop.is_medical_shop)
        self.assertTrue(rx_drug.requires_prescription)

        # Citizen submits prescription request to pharmacist
        self.client.force_authenticate(user=self.citizen)
        req_res = self.client.post("/api/v1/orders/service-requests/", {
            "shop": shop.id,
            "request_type": "prescription",
            "description": "Prescription for Amoxicillin 500mg from Dr. Nair",
            "customer_phone": self.citizen.phone_number
        }, format='json')
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        req_id = req_res.data['id']

        # Pharmacist reviews and responds with quote
        self.client.force_authenticate(user=owner)
        resp_res = self.client.post(f"/api/v1/orders/service-requests/{req_id}/respond/", {
            "status": "accepted",
            "response": "Medicine is in stock. Please bring original physical prescription at pickup.",
            "quoted_price": 120.00
        }, format='json')
        self.assertEqual(resp_res.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_res.data['status'], "accepted")

    def test_beauty_parlour_flow(self):
        """Beauty Parlour: Service duration, appointment booking, and confirmation."""
        owner = User.objects.create_user(
            phone_number="9847555004", password="password123", full_name="Parlour Stylist", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="Bridal & Beauty Salon",
            business_type=ShopCategory.BusinessType.BEAUTY_PARLOUR,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        shop = Shop.objects.create(
            owner=owner, name="Rose Beauty Lounge", category=cat, area=self.area, ward_number=2,
            contact_phone="9847555004", is_verified=True, is_open=True
        )
        facial = Product.objects.create(
            shop=shop, name="Fruit Facial", price=650.00, service_duration_minutes=45, is_available=True
        )

        self.assertTrue(shop.is_beauty_parlour)
        self.assertTrue(shop.is_service_based)
        self.assertEqual(facial.duration_display, "45 മിനിറ്റ്")

        # Citizen books appointment
        self.client.force_authenticate(user=self.citizen)
        book_res = self.client.post("/api/v1/orders/bookings/", {
            "shop": shop.id,
            "service": facial.id,
            "booking_date": "2026-11-15",
            "time_slot": "03:00 PM - 04:00 PM",
            "customer_phone": self.citizen.phone_number
        }, format='json')
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)
        booking_id = book_res.data['id']

        # Owner confirms appointment
        self.client.force_authenticate(user=owner)
        confirm_res = self.client.post(f"/api/v1/orders/bookings/{booking_id}/update-status/", {
            "status": Booking.Status.CONFIRMED
        }, format='json')
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_res.data['status'], Booking.Status.CONFIRMED)

    def test_restaurant_flow(self):
        """Restaurant: Dining menu ordering and delivery radius configuration."""
        owner = User.objects.create_user(
            phone_number="9847555005", password="password123", full_name="Chef Ramesh", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="Restaurant & Cafe",
            business_type=ShopCategory.BusinessType.RESTAURANT,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        shop = Shop.objects.create(
            owner=owner, name="Malabar Spice Kitchen", category=cat, area=self.area, ward_number=2,
            contact_phone="9847555005", delivery_available=True, delivery_radius_km=7.5,
            is_verified=True, is_open=True
        )
        biryani = Product.objects.create(
            shop=shop, name="Malabar Chicken Biryani", price=180.00, unit="1 pot", is_available=True
        )

        self.assertTrue(shop.is_restaurant)
        self.assertTrue(shop.delivery_available)
        self.assertEqual(float(shop.delivery_radius_km), 7.5)

        # Customer orders biryani
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post("/api/v1/orders/orders/", {
            "shop_id": shop.id,
            "delivery_type": "delivery",
            "delivery_address": "Flat 3B, Sunshine Apartments",
            "items": [{"product_id": biryani.id, "quantity": 2}]
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(res.data['total_amount']), 360.00)

    def test_repair_shop_flow(self):
        """Repair Shop: Custom diagnostic request and price quote response."""
        owner = User.objects.create_user(
            phone_number="9847555006", password="password123", full_name="Technician Shaji", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="Electronics & Repair",
            business_type=ShopCategory.BusinessType.REPAIR,
            interaction_mode=ShopCategory.InteractionMode.REQUEST
        )
        shop = Shop.objects.create(
            owner=owner, name="FastFix TV & Appliance Repair", category=cat, area=self.area, ward_number=3,
            contact_phone="9847555006", is_verified=True, is_open=True
        )

        self.assertTrue(shop.is_repair_shop)
        self.assertTrue(shop.is_service_based)

        # Citizen submits appliance diagnostic request
        self.client.force_authenticate(user=self.citizen)
        req_res = self.client.post("/api/v1/orders/service-requests/", {
            "shop": shop.id,
            "request_type": "general",
            "description": "Mixer grinder motor not spinning, burning smell",
            "customer_phone": self.citizen.phone_number
        }, format='json')
        self.assertEqual(req_res.status_code, status.HTTP_201_CREATED)
        req_id = req_res.data['id']

        # Technician provides diagnostic quote
        self.client.force_authenticate(user=owner)
        resp_res = self.client.post(f"/api/v1/orders/service-requests/{req_id}/respond/", {
            "status": "accepted",
            "response": "Armature replacement required. Estimate ₹350 including labour.",
            "quoted_price": 350.00
        }, format='json')
        self.assertEqual(resp_res.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp_res.data['quoted_price']), 350.00)

    def test_other_service_provider_flow(self):
        """Other Service: Hourly/unit pricing and slot reservations."""
        owner = User.objects.create_user(
            phone_number="9847555007", password="password123", full_name="Akshaya Operator", role=User.Role.SHOP_OWNER
        )
        cat = ShopCategory.objects.create(
            name="Akshaya & Online Services",
            business_type=ShopCategory.BusinessType.OTHER_SERVICE,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        shop = Shop.objects.create(
            owner=owner, name="Ward 1 Akshaya Center", category=cat, area=self.area, ward_number=1,
            contact_phone="9847555007", is_verified=True, is_open=True
        )
        aadhaar_service = Product.objects.create(
            shop=shop, name="Aadhaar Card Biometric Update", price=50.00, service_duration_minutes=20, is_available=True
        )

        self.assertTrue(shop.is_service_based)
        self.assertEqual(aadhaar_service.duration_display, "20 മിനിറ്റ്")

        # Citizen books Akshaya slot
        self.client.force_authenticate(user=self.citizen)
        book_res = self.client.post("/api/v1/orders/bookings/", {
            "shop": shop.id,
            "service": aadhaar_service.id,
            "booking_date": "2026-11-20",
            "time_slot": "11:00 AM - 11:20 AM",
            "customer_phone": self.citizen.phone_number
        }, format='json')
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED)


class Phase4TrustAndModerationTests(TestCase):
    """
    Validation for Trust, Moderation, Verified Businesses, Reviews, and Ratings under Phase 4:
    - Verified businesses filtering and badges.
    - Verified buyer ratings and reviews.
    - Preventing duplicate reviews and review manipulation.
    """
    def setUp(self):
        self.client = APIClient()
        self.area = Area.objects.create(name="East Ward", district="Palakkad")
        self.category = ShopCategory.objects.create(
            name="General Merchant",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )

        self.shop_owner = User.objects.create_user(
            phone_number="9847990011",
            password="password123",
            full_name="Verified Merchant",
            role=User.Role.SHOP_OWNER
        )

        self.shop = Shop.objects.create(
            owner=self.shop_owner,
            name="Palakkad Pure Spices",
            category=self.category,
            area=self.area,
            ward_number=2,
            contact_phone="9847990011",
            is_verified=True,
            is_open=True
        )

        self.citizen = User.objects.create_user(
            phone_number="9847990022",
            password="password123",
            full_name="Suresh Citizen",
            role=User.Role.CITIZEN
        )

        self.other_citizen = User.objects.create_user(
            phone_number="9847990033",
            password="password123",
            full_name="Deepak Citizen",
            role=User.Role.CITIZEN
        )

    def test_verified_business_flag_and_admin_approval(self):
        """Unverified shops submitted by citizens require staff verification to appear publicly."""
        unverified_shop = Shop.objects.create(
            owner=self.other_citizen,
            name="Unverified Street Stall",
            category=self.category,
            area=self.area,
            ward_number=2,
            contact_phone="9847990033",
            is_verified=False
        )

        # Public visitors only see verified shops
        res = self.client.get("/api/v1/shops/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [s['id'] for s in res.data.get('results', res.data)]
        self.assertIn(self.shop.id, ids)
        self.assertNotIn(unverified_shop.id, ids)

    def test_customer_can_post_review_and_verified_buyer_badge(self):
        """Customer who completed an order receives verified buyer badge on review."""
        # Create completed order for Suresh
        Order.objects.create(
            customer=self.citizen,
            shop=self.shop,
            status=Order.Status.COMPLETED,
            total_amount=500.00
        )

        self.client.force_authenticate(user=self.citizen)
        url = "/api/v1/shops/reviews/"
        payload = {
            "shop": self.shop.id,
            "rating": 5,
            "comment": "Authentic fresh spices, very fast delivery!"
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_verified_buyer'])
        self.assertEqual(res.data['rating'], 5)

    def test_unverified_customer_review_does_not_get_verified_buyer_badge(self):
        """User who has never bought from the shop can leave a review, but is_verified_buyer is False."""
        self.client.force_authenticate(user=self.other_citizen)
        url = "/api/v1/shops/reviews/"
        payload = {
            "shop": self.shop.id,
            "rating": 4,
            "comment": "Nice customer service when I visited the store."
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data['is_verified_buyer'])

    def test_prevent_duplicate_review_per_shop(self):
        """User cannot submit duplicate reviews for the same shop."""
        Review.objects.create(
            shop=self.shop,
            user=self.citizen,
            rating=5,
            comment="First review"
        )

        self.client.force_authenticate(user=self.citizen)
        url = "/api/v1/shops/reviews/"
        res = self.client.post(url, {
            "shop": self.shop.id,
            "rating": 4,
            "comment": "Second review attempt"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# Progress Tracking Module Tests (Admin & Individual Shop)
# ==============================================================================

class ShopProgressTrackingModuleTests(TestCase):
    """
    Validation for Ente Naadu Admin & Shop Progress Tracking Module:
    1. Admin Progress Overview API & Web View
    2. Shop Owner Individual Progress API & Web View
    3. Strict Object-level Privacy & Anti-BOLA (Shop A cannot view Shop B's progress)
    4. Category-Aware Progress Rules (Product-based vs Service-based)
    5. Real-time Progress recalculation upon adding Products, GPS, Verification
    6. Privacy: Customer private data is never exposed in progress payloads
    """

    def setUp(self):
        self.api_client = APIClient()
        self.web_client = Client()
        self.area = Area.objects.create(name="Thrissur Town", district="Thrissur")

        # 1. Super Admin
        self.admin = User.objects.create_superuser(
            phone_number="9899000001",
            password="AdminPass123",
            full_name="Panchayat Super Admin"
        )

        # 2. Shop Owner A (Product-based General Store)
        self.owner_a = User.objects.create_user(
            phone_number="9899000002",
            password="OwnerAPass123",
            full_name="Merchant A",
            role=User.Role.SHOP_OWNER
        )
        self.cat_general = ShopCategory.objects.create(
            name="General Provisions",
            business_type=ShopCategory.BusinessType.GENERAL,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        self.shop_a = Shop.objects.create(
            owner=self.owner_a,
            name="Merchant A Grocery Store",
            category=self.cat_general,
            area=self.area,
            ward_number=1,
            address="Market Road, Thrissur",
            contact_phone="9899000002",
            opening_time="08:00:00",
            closing_time="20:00:00",
            latitude=10.5276,
            longitude=76.2144,
            is_verified=False,
            is_open=True
        )

        # 3. Shop Owner B (Service-based Beauty Parlour)
        self.owner_b = User.objects.create_user(
            phone_number="9899000003",
            password="OwnerBPass123",
            full_name="Stylist B",
            role=User.Role.SHOP_OWNER
        )
        self.cat_parlour = ShopCategory.objects.create(
            name="Beauty Salon",
            business_type=ShopCategory.BusinessType.BEAUTY_PARLOUR,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        self.shop_b = Shop.objects.create(
            owner=self.owner_b,
            name="Stylist B Parlour",
            category=self.cat_parlour,
            area=self.area,
            ward_number=2,
            address="College Junction",
            contact_phone="9899000003",
            is_verified=True,
            is_open=True
        )

        # 4. Citizen Customer
        self.citizen = User.objects.create_user(
            phone_number="9899000004",
            password="CitizenPass123",
            full_name="Citizen Venu",
            role=User.Role.CITIZEN
        )

    def test_admin_can_view_all_shops_progress_api_and_web(self):
        """Admin can access admin progress overview both via REST API and Web view."""
        # 1. REST API
        self.api_client.force_authenticate(user=self.admin)
        api_res = self.api_client.get("/api/v1/shops/shops/admin-progress/")
        self.assertEqual(api_res.status_code, status.HTTP_200_OK)
        self.assertIn("total_shops", api_res.data)
        self.assertIn("average_progress", api_res.data)
        self.assertIn("category_stats", api_res.data)
        self.assertIn("shops_progress", api_res.data)
        self.assertEqual(api_res.data["total_shops"], 2)

        # 2. Web Portal View
        self.web_client.force_login(self.admin)
        web_res = self.web_client.get(reverse('admin-shops-progress'))
        self.assertEqual(web_res.status_code, 200)
        self.assertContains(web_res, "വ്യാപാരികളുടെ പുരോഗതി നിരീക്ഷണം")
        self.assertContains(web_res, self.shop_a.name)
        self.assertContains(web_res, self.shop_b.name)

    def test_shop_owner_cannot_access_admin_progress_overview(self):
        """Regular shop owner calling admin progress overview receives 403 Forbidden."""
        # 1. REST API -> 403
        self.api_client.force_authenticate(user=self.owner_a)
        api_res = self.api_client.get("/api/v1/shops/shops/admin-progress/")
        self.assertEqual(api_res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Web Portal View -> Redirect with error message
        self.web_client.force_login(self.owner_a)
        web_res = self.web_client.get(reverse('admin-shops-progress'))
        self.assertEqual(web_res.status_code, 302)

    def test_shop_owner_can_view_own_shop_progress(self):
        """Shop Owner A can view their own shop progress via API and Web."""
        # 1. REST API
        self.api_client.force_authenticate(user=self.owner_a)
        api_res = self.api_client.get(f"/api/v1/shops/shops/{self.shop_a.id}/progress/")
        self.assertEqual(api_res.status_code, status.HTTP_200_OK)
        self.assertEqual(api_res.data["shop_id"], self.shop_a.id)
        self.assertIn("overall_percentage", api_res.data)
        self.assertIn("checklist", api_res.data)
        self.assertIn("sections", api_res.data)

        # 2. Web Portal View
        self.web_client.force_login(self.owner_a)
        web_res = self.web_client.get(reverse('shop-progress-detail', args=[self.shop_a.id]))
        self.assertEqual(web_res.status_code, 200)
        self.assertContains(web_res, self.shop_a.name)
        self.assertContains(web_res, "പൂർത്തീകരണ ചെക്ക്‌ലിസ്റ്റ്")

    def test_shop_a_owner_cannot_view_shop_b_progress_anti_bola(self):
        """Shop Owner A cannot view Shop B's progress (Anti-BOLA/IDOR protection -> 403 Forbidden)."""
        # 1. REST API -> 403
        self.api_client.force_authenticate(user=self.owner_a)
        api_res = self.api_client.get(f"/api/v1/shops/shops/{self.shop_b.id}/progress/")
        self.assertEqual(api_res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Web Portal View -> 403 PermissionDenied
        self.web_client.force_login(self.owner_a)
        web_res = self.web_client.get(reverse('shop-progress-detail', args=[self.shop_b.id]))
        self.assertEqual(web_res.status_code, 403)

    def test_category_aware_progress_calculation_and_updates(self):
        """
        Tests category-aware progress calculation and real-time score updates
        upon adding products, updating location, and admin verification.
        """
        # Initial score of Shop A (No products yet)
        initial_progress = self.shop_a.get_progress()
        initial_score = initial_progress["overall_percentage"]
        self.assertEqual(initial_progress["sections"]["catalog"]["score"], 0)

        # Add 1 product
        p1 = Product.objects.create(
            shop=self.shop_a,
            name="Coconut Oil",
            price=220.00,
            is_available=True
        )
        progress_after_1 = self.shop_a.get_progress()
        self.assertGreater(progress_after_1["overall_percentage"], initial_score)
        self.assertEqual(progress_after_1["sections"]["catalog"]["score"], 15) # 10 (1+ product) + 5 (in stock)

        # Add 2 more products to reach >= 3 products
        Product.objects.create(shop=self.shop_a, name="Jaggery", price=60.00, is_available=True)
        Product.objects.create(shop=self.shop_a, name="Cardamom", price=150.00, is_available=True)
        progress_after_3 = self.shop_a.get_progress()
        self.assertEqual(progress_after_3["sections"]["catalog"]["score"], 25) # Max catalog score

        # Admin approves shop -> Verification score updates (+10)
        score_before_verify = progress_after_3["overall_percentage"]
        self.shop_a.is_verified = True
        self.shop_a.save(update_fields=['is_verified'])
        progress_verified = self.shop_a.get_progress()
        self.assertEqual(progress_verified["sections"]["verification"]["score"], 10)
        self.assertEqual(progress_verified["overall_percentage"], score_before_verify + 10)

    def test_customer_private_data_not_exposed_in_progress_data(self):
        """Ensures progress tracking payloads strictly protect citizen privacy."""
        # Create an order with private customer information
        order = Order.objects.create(
            customer=self.citizen,
            shop=self.shop_a,
            delivery_type=Order.DeliveryType.HOME_DELIVERY,
            delivery_address="Secret House #99, Private Colony",
            customer_phone="9899000004",
            total_amount=500.00,
            status=Order.Status.COMPLETED
        )

        progress = self.shop_a.get_progress()
        # Verify aggregate counts exist but private data does not leak
        self.assertEqual(progress["metrics"]["total_orders"], 1)
        self.assertEqual(progress["metrics"]["completed_orders"], 1)

        progress_str = str(progress)
        self.assertNotIn("Secret House", progress_str)
        self.assertNotIn("Private Colony", progress_str)
        self.assertNotIn(self.citizen.password, progress_str)


# ==============================================================================
# Shop Working Hours & Real-Time IST Business Status Tests
# ==============================================================================

class ShopWorkingHoursAndStatusTests(TestCase):
    """
    Test suite covering 8 scenarios for Shop Working Hours & Business Status:
    1. Before opening time -> CLOSED
    2. During opening time -> OPEN
    3. After closing time -> CLOSED
    4. Weekly holiday (Closed / Holiday) -> CLOSED TODAY
    5. Temporarily Closed emergency override -> CLOSED (Temporarily Closed)
    6. Working hours not set -> Hours not set
    7. Shop owner saves changes -> New hours persisted and progress updated
    8. Unauthorized user attempts to edit another shop's hours -> 403 Forbidden
    """

    def setUp(self):
        import zoneinfo
        self.kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        self.web_client = Client()
        self.api_client = APIClient()

        self.area = Area.objects.create(name="Aluva Town", district="Ernakulam")
        self.category = ShopCategory.objects.create(
            name="Supermarket",
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )

        # Owner 1 & Shop 1
        self.owner1 = User.objects.create_user(
            phone_number="9876500001",
            password="Password123!",
            full_name="Kishore Kumar",
            role=User.Role.SHOP_OWNER
        )
        self.shop1 = Shop.objects.create(
            owner=self.owner1,
            name="Kishore Department Store",
            category=self.category,
            area=self.area,
            ward_number=5,
            address="Aluva Railway Station Road",
            contact_phone="9876500001",
            is_verified=True,
            is_open=True
        )

        # Owner 2 & Shop 2 (Attacker)
        self.owner2 = User.objects.create_user(
            phone_number="9876500002",
            password="Password123!",
            full_name="Attacker Shopkeeper",
            role=User.Role.SHOP_OWNER
        )
        self.shop2 = Shop.objects.create(
            owner=self.owner2,
            name="Attacker Corner Shop",
            category=self.category,
            area=self.area,
            ward_number=6,
            address="Market Road",
            contact_phone="9876500002",
            is_verified=True,
            is_open=True
        )

        # Standard citizen
        self.citizen = User.objects.create_user(
            phone_number="9876500003",
            password="Password123!",
            full_name="Anjali Nair",
            role=User.Role.CITIZEN
        )

        # Configure Monday to Saturday (0 to 5) as 09:00 to 20:00
        # and Sunday (6) as Closed
        from datetime import time
        for d in range(6):
            ShopWorkingHour.objects.create(
                shop=self.shop1,
                day=d,
                opening_time=time(9, 0),
                closing_time=time(20, 0),
                is_closed=False
            )
        ShopWorkingHour.objects.create(
            shop=self.shop1,
            day=6,
            opening_time=None,
            closing_time=None,
            is_closed=True
        )

    def test_scenario_1_before_opening_time(self):
        """Scenario 1: Tested before opening time (e.g. 08:30 AM on Monday) -> Status is CLOSED NOW."""
        from datetime import datetime
        # Monday 08:30:00 IST
        test_dt = datetime(2026, 11, 2, 8, 30, 0, tzinfo=self.kolkata_tz)
        status = self.shop1.get_business_status(now=test_dt)
        self.assertEqual(status['status_code'], 'CLOSED')
        self.assertEqual(status['status_label'], 'CLOSED NOW')
        self.assertFalse(status['is_open_now'])

    def test_scenario_2_during_opening_time(self):
        """Scenario 2: Tested during operating hours (e.g. 02:30 PM on Monday) -> Status is OPEN NOW."""
        from datetime import datetime
        # Monday 14:30:00 IST
        test_dt = datetime(2026, 11, 2, 14, 30, 0, tzinfo=self.kolkata_tz)
        status = self.shop1.get_business_status(now=test_dt)
        self.assertEqual(status['status_code'], 'OPEN')
        self.assertEqual(status['status_label'], 'OPEN NOW')
        self.assertTrue(status['is_open_now'])

    def test_scenario_3_after_closing_time(self):
        """Scenario 3: Tested after closing hours (e.g. 09:15 PM on Monday) -> Status is CLOSED NOW."""
        from datetime import datetime
        # Monday 21:15:00 IST
        test_dt = datetime(2026, 11, 2, 21, 15, 0, tzinfo=self.kolkata_tz)
        status = self.shop1.get_business_status(now=test_dt)
        self.assertEqual(status['status_code'], 'CLOSED')
        self.assertEqual(status['status_label'], 'CLOSED NOW')
        self.assertFalse(status['is_open_now'])

    def test_scenario_4_weekly_holiday(self):
        """Scenario 4: Tested on scheduled closed day (e.g. Sunday noon) -> Status is CLOSED TODAY."""
        from datetime import datetime
        # Sunday 12:00:00 IST (2026-11-08 is Sunday)
        test_dt = datetime(2026, 11, 8, 12, 0, 0, tzinfo=self.kolkata_tz)
        status = self.shop1.get_business_status(now=test_dt)
        self.assertEqual(status['status_code'], 'CLOSED_TODAY')
        self.assertEqual(status['status_label'], 'CLOSED TODAY')
        self.assertFalse(status['is_open_now'])

    def test_scenario_5_temporarily_closed_override(self):
        """
        Scenario 5: When temporarily closed emergency toggle is active,
        status must NEVER show OPEN, even when current time falls within normal operating schedule.
        """
        from datetime import datetime
        self.shop1.is_temporarily_closed = True
        self.shop1.temporary_close_reason = "കടയിൽ വയറിംഗ് നവീകരണം നടക്കുന്നു."
        self.shop1.save()

        # Monday 11:00 AM (normally open)
        test_dt = datetime(2026, 11, 2, 11, 0, 0, tzinfo=self.kolkata_tz)
        status = self.shop1.get_business_status(now=test_dt)
        self.assertEqual(status['status_code'], 'TEMPORARILY_CLOSED')
        self.assertFalse(status['is_open_now'])
        self.assertTrue(status['is_temporarily_closed'])
        self.assertIn("വയറിംഗ്", status['reason'])

    def test_scenario_6_working_hours_not_set(self):
        """Scenario 6: When a shop has not configured any schedule -> Status is 'Hours not set'."""
        status = self.shop2.get_business_status()
        self.assertEqual(status['status_code'], 'HOURS_NOT_SET')
        self.assertEqual(status['status_label'], 'Hours not set')

    def test_scenario_7_shop_owner_saves_hours_form_successfully(self):
        """
        Scenario 7: Shop owner posts schedule form to /dashboard/shop/<id>/hours/.
        Form saves all 7 days, updates fallback shop hours, shows success, and redirects to dashboard.
        """
        self.web_client.force_login(self.owner2)
        url = reverse('shop-hours-edit', args=[self.shop2.id])

        post_data = {
            'is_temporarily_closed': '',
            'temporary_close_reason': '',
            # Monday to Friday: 08:30 to 21:00
            'open_time_0': '08:30', 'close_time_0': '21:00',
            'open_time_1': '08:30', 'close_time_1': '21:00',
            'open_time_2': '08:30', 'close_time_2': '21:00',
            'open_time_3': '08:30', 'close_time_3': '21:00',
            'open_time_4': '08:30', 'close_time_4': '21:00',
            # Saturday: 09:00 to 18:00
            'open_time_5': '09:00', 'close_time_5': '18:00',
            # Sunday: Closed
            'closed_6': 'on',
        }

        response = self.web_client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('shop-dashboard'))

        # Verify DB entries
        self.assertEqual(self.shop2.working_hours.count(), 7)
        mon_hour = self.shop2.working_hours.get(day=0)
        self.assertEqual(mon_hour.opening_time.strftime('%H:%M'), '08:30')
        self.assertEqual(mon_hour.closing_time.strftime('%H:%M'), '21:00')
        self.assertFalse(mon_hour.is_closed)

        sun_hour = self.shop2.working_hours.get(day=6)
        self.assertTrue(sun_hour.is_closed)

        # Fallback fields updated
        self.shop2.refresh_from_db()
        self.assertEqual(self.shop2.opening_time.strftime('%H:%M'), '08:30')
        self.assertEqual(self.shop2.closing_time.strftime('%H:%M'), '21:00')

        # Progress check verifies hours are counted
        progress = self.shop2.get_progress()
        self.assertEqual(progress['sections']['hours']['score'], 10)

    def test_scenario_8_unauthorized_user_tampering_blocked(self):
        """
        Scenario 8: Anti-BOLA Security.
        Owner 1 attempts to modify Owner 2's shop hours (/dashboard/shop/<shop2.id>/hours/) -> 403 Forbidden.
        Citizen attempts to access hours edit -> 403 Forbidden.
        """
        # Owner 1 tampering with Shop 2
        self.web_client.force_login(self.owner1)
        url_shop2 = reverse('shop-hours-edit', args=[self.shop2.id])
        get_res = self.web_client.get(url_shop2)
        self.assertEqual(get_res.status_code, 403)

        post_res = self.web_client.post(url_shop2, {'open_time_0': '10:00'})
        self.assertEqual(post_res.status_code, 403)

        # Citizen tampering
        self.web_client.force_login(self.citizen)
        cit_res = self.web_client.get(url_shop2)
        self.assertEqual(cit_res.status_code, 403)


# ==============================================================================
# Category-Based Rating System Tests
# ==============================================================================

class CategoryBasedRatingSystemTests(TestCase):
    """
    Comprehensive verification for Category-Based Rating System:
    1. Dynamic rating criteria tailored to shop category / business type.
    2. Multi-criteria ratings creation for completed orders and completed bookings.
    3. Rejection of reviews for pending, confirmed, or cancelled orders/bookings.
    4. Rejection of unverified customers without completed interaction.
    5. Prevention of shop owners reviewing their own shops.
    6. Enforcement of 1–5 star boundaries.
    7. Prevention of duplicate reviews per shop.
    8. Mathematical accuracy of overall rating (strictly non-compounded average) and criteria averages.
    9. Future category support: dynamic criteria configuration and historical snapshot preservation.
    10. REST API rating-summary, rating-criteria, and can-review endpoints.
    11. Web portal review submission view with CSRF and validation.
    """
    def setUp(self):
        self.api_client = APIClient()
        self.web_client = Client()

        self.area = Area.objects.create(name="Kottayam Town", district="Kottayam")

        # Business categories
        self.cat_general = ShopCategory.objects.create(
            name="General Supermarket",
            business_type=ShopCategory.BusinessType.GENERAL,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        self.cat_parlour = ShopCategory.objects.create(
            name="Beauty Parlour & Salon",
            business_type=ShopCategory.BusinessType.BEAUTY_PARLOUR,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )
        self.cat_repair = ShopCategory.objects.create(
            name="Appliance Repair Shop",
            business_type=ShopCategory.BusinessType.REPAIR,
            interaction_mode=ShopCategory.InteractionMode.REQUEST
        )
        self.cat_restaurant = ShopCategory.objects.create(
            name="Kerala Restaurant",
            business_type=ShopCategory.BusinessType.RESTAURANT,
            interaction_mode=ShopCategory.InteractionMode.ORDER
        )
        self.cat_service = ShopCategory.objects.create(
            name="Akshaya Center",
            business_type=ShopCategory.BusinessType.OTHER_SERVICE,
            interaction_mode=ShopCategory.InteractionMode.BOOKING
        )

        # Users
        self.owner_general = User.objects.create_user(
            phone_number="9847000101", password="password123", full_name="General Merchant", role=User.Role.SHOP_OWNER
        )
        self.owner_parlour = User.objects.create_user(
            phone_number="9847000102", password="password123", full_name="Parlour Stylist", role=User.Role.SHOP_OWNER
        )
        self.customer1 = User.objects.create_user(
            phone_number="9847000201", password="password123", full_name="Anjali Nair", role=User.Role.CITIZEN
        )
        self.customer2 = User.objects.create_user(
            phone_number="9847000202", password="password123", full_name="Rahul Varma", role=User.Role.CITIZEN
        )
        self.unverified_customer = User.objects.create_user(
            phone_number="9847000203", password="password123", full_name="Unverified Visitor", role=User.Role.CITIZEN
        )
        self.admin = User.objects.create_superuser(
            phone_number="9847000999", password="adminpassword", full_name="System Admin"
        )

        # Shops
        self.shop_general = Shop.objects.create(
            owner=self.owner_general,
            name="Kottayam Fresh Provisions",
            category=self.cat_general,
            area=self.area,
            ward_number=1,
            contact_phone="9847000101",
            is_verified=True,
            is_open=True
        )
        self.shop_parlour = Shop.objects.create(
            owner=self.owner_parlour,
            name="Lotus Beauty Salon",
            category=self.cat_parlour,
            area=self.area,
            ward_number=2,
            contact_phone="9847000102",
            is_verified=True,
            is_open=True
        )

        # Completed order for customer1 at shop_general
        self.order_completed = Order.objects.create(
            customer=self.customer1,
            shop=self.shop_general,
            status=Order.Status.COMPLETED,
            total_amount=450.00
        )

        # Pending order for customer2 at shop_general
        self.order_pending = Order.objects.create(
            customer=self.customer2,
            shop=self.shop_general,
            status=Order.Status.PENDING,
            total_amount=200.00
        )

        # Completed booking for customer1 at shop_parlour
        self.booking_completed = Booking.objects.create(
            customer=self.customer1,
            shop=self.shop_parlour,
            booking_date="2026-11-01",
            time_slot="10:00 AM",
            customer_phone=self.customer1.phone_number,
            status=Booking.Status.COMPLETED
        )

        # Pending booking for customer2 at shop_parlour
        self.booking_pending = Booking.objects.create(
            customer=self.customer2,
            shop=self.shop_parlour,
            booking_date="2026-11-02",
            time_slot="11:00 AM",
            customer_phone=self.customer2.phone_number,
            status=Booking.Status.PENDING
        )

    def test_dynamic_rating_criteria_for_all_business_categories(self):
        """
        Verify that get_rating_criteria() dynamically returns criteria tailored
        specifically to each of the distinct shop categories and business types.
        """
        # General Shop criteria
        gen_criteria = self.shop_general.get_rating_criteria()
        gen_slugs = [c['slug'] for c in gen_criteria]
        self.assertIn('cleanliness', gen_slugs)
        self.assertIn('pricing', gen_slugs)
        self.assertIn('quality', gen_slugs)
        self.assertIn('service', gen_slugs)

        # Beauty Parlour criteria
        parlour_criteria = self.shop_parlour.get_rating_criteria()
        parlour_slugs = [c['slug'] for c in parlour_criteria]
        self.assertIn('hygiene', parlour_slugs)
        self.assertIn('service_quality', parlour_slugs)
        self.assertIn('staff_behavior', parlour_slugs)
        self.assertIn('ambience', parlour_slugs)
        self.assertIn('value_for_money', parlour_slugs)

        # Restaurant criteria
        shop_rest = Shop.objects.create(
            owner=self.owner_general, name="Taste of Kerala", category=self.cat_restaurant,
            area=self.area, ward_number=3, contact_phone="9847000103"
        )
        rest_criteria = shop_rest.get_rating_criteria()
        rest_slugs = [c['slug'] for c in rest_criteria]
        self.assertIn('food_taste', rest_slugs)
        self.assertIn('hygiene', rest_slugs)
        self.assertIn('service_speed', rest_slugs)
        self.assertIn('packaging', rest_slugs)

        # Repair Shop criteria
        shop_rep = Shop.objects.create(
            owner=self.owner_general, name="QuickFix Electronics", category=self.cat_repair,
            area=self.area, ward_number=4, contact_phone="9847000104"
        )
        rep_criteria = shop_rep.get_rating_criteria()
        rep_slugs = [c['slug'] for c in rep_criteria]
        self.assertIn('diagnostic_accuracy', rep_slugs)
        self.assertIn('repair_quality', rep_slugs)
        self.assertIn('pricing_transparency', rep_slugs)
        self.assertIn('turnaround_time', rep_slugs)

    def test_order_based_review_creation_with_criteria_api(self):
        """
        Customer who completed an order can submit a review with 1-5 overall rating,
        general comment, and multi-criteria breakdown scores.
        """
        self.api_client.force_authenticate(user=self.customer1)
        url = "/api/v1/shops/reviews/"
        payload = {
            "shop": self.shop_general.id,
            "rating": 5,
            "comment": "Excellent fresh groceries and very courteous staff!",
            "order_id": self.order_completed.id,
            "criteria_ratings": [
                {"criterion_slug": "cleanliness", "rating": 5, "feedback": "Spotless aisles"},
                {"criterion_slug": "pricing", "rating": 4, "feedback": "Reasonable wholesale rates"},
                {"criterion_slug": "quality", "rating": 5, "feedback": "Top quality fresh veggies"},
                {"criterion_slug": "service", "rating": 5, "feedback": "Super fast checkout"}
            ]
        }
        res = self.api_client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_verified_buyer'])
        self.assertEqual(res.data['rating'], 5)
        self.assertEqual(res.data['order'], self.order_completed.id)

        # Verify criterion ratings in DB with snapshot
        rev = Review.objects.get(id=res.data['id'])
        self.assertEqual(rev.criterion_ratings.count(), 4)
        c_clean = rev.criterion_ratings.get(criterion_slug="cleanliness")
        self.assertEqual(c_clean.rating, 5)
        self.assertEqual(c_clean.feedback, "Spotless aisles")
        self.assertTrue(len(c_clean.criterion_name) > 0)

    def test_booking_based_review_creation_with_criteria_api(self):
        """
        Customer who completed a booking can submit a verified review with category criteria.
        """
        self.api_client.force_authenticate(user=self.customer1)
        url = "/api/v1/shops/reviews/"
        payload = {
            "shop": self.shop_parlour.id,
            "rating": 5,
            "comment": "Wonderful facial and calming ambience!",
            "booking_id": self.booking_completed.id,
            "criteria_ratings": [
                {"criterion_slug": "hygiene", "rating": 5, "feedback": "Sanitized equipment"},
                {"criterion_slug": "service_quality", "rating": 5, "feedback": "Great beautician"},
                {"criterion_slug": "staff_behavior", "rating": 5, "feedback": "Friendly and helpful"},
                {"criterion_slug": "ambience", "rating": 4, "feedback": "Good music and lighting"},
                {"criterion_slug": "value_for_money", "rating": 5, "feedback": "Worth every rupee"}
            ]
        }
        res = self.api_client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_verified_buyer'])
        self.assertEqual(res.data['booking'], self.booking_completed.id)

        rev = Review.objects.get(id=res.data['id'])
        self.assertEqual(rev.criterion_ratings.count(), 5)

    def test_rejection_of_pending_or_uncompleted_order_and_booking(self):
        """
        Reviews must be strictly restricted to completed orders and bookings.
        Pending, confirmed, or cancelled transactions must be rejected.
        """
        self.api_client.force_authenticate(user=self.customer2)
        url = "/api/v1/shops/reviews/"

        # Attempt to review using a pending order -> 400 Bad Request
        res_order = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 5,
            "comment": "Trying to review before order delivery",
            "order_id": self.order_pending.id
        }, format='json')
        self.assertEqual(res_order.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed", str(res_order.data).lower())

        # Attempt to review using a pending booking -> 400 Bad Request
        res_booking = self.api_client.post(url, {
            "shop": self.shop_parlour.id,
            "rating": 4,
            "comment": "Trying to review before appointment",
            "booking_id": self.booking_pending.id
        }, format='json')
        self.assertEqual(res_booking.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed", str(res_booking.data).lower())

    def test_unverified_customer_without_completed_transaction_rejected(self):
        """
        User with no completed order or booking cannot submit a verified review.
        """
        self.api_client.force_authenticate(user=self.unverified_customer)
        url = "/api/v1/shops/reviews/"
        res = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 5,
            "comment": "I have never ordered from this shop"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed order or booking", str(res.data).lower())

    def test_shop_owner_cannot_review_own_shop(self):
        """
        Shop owners are strictly prevented from posting reviews for their own shop.
        """
        self.api_client.force_authenticate(user=self.owner_general)
        url = "/api/v1/shops/reviews/"
        res = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 5,
            "comment": "Self promotion of my shop"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("own shop", str(res.data).lower())

    def test_duplicate_review_per_shop_prevented(self):
        """
        A customer can only review a shop once. Duplicate reviews are blocked.
        """
        Review.objects.create(
            shop=self.shop_general,
            user=self.customer1,
            order=self.order_completed,
            rating=5,
            comment="First completed review"
        )

        self.api_client.force_authenticate(user=self.customer1)
        url = "/api/v1/shops/reviews/"
        res = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 4,
            "comment": "Second review attempt by same customer"
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already reviewed", str(res.data).lower())

    def test_rating_boundary_validation_enforced(self):
        """
        Ratings must strictly be between 1 and 5. Values of 0, 6, or negative are rejected.
        """
        self.api_client.force_authenticate(user=self.customer1)
        url = "/api/v1/shops/reviews/"

        # Overall rating 6 -> Rejected
        res_high = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 6,
            "comment": "Rating too high",
            "order_id": self.order_completed.id
        }, format='json')
        self.assertEqual(res_high.status_code, status.HTTP_400_BAD_REQUEST)

        # Overall rating 0 -> Rejected
        res_zero = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 0,
            "comment": "Rating zero",
            "order_id": self.order_completed.id
        }, format='json')
        self.assertEqual(res_zero.status_code, status.HTTP_400_BAD_REQUEST)

        # Criterion rating 6 -> Rejected
        res_crit = self.api_client.post(url, {
            "shop": self.shop_general.id,
            "rating": 5,
            "comment": "Criterion too high",
            "order_id": self.order_completed.id,
            "criteria_ratings": [{"criterion_slug": "cleanliness", "rating": 6}]
        }, format='json')
        self.assertEqual(res_crit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mathematical_accuracy_of_rating_summary_and_non_compounded_average(self):
        """
        Verifies requirement 4:
        - overall_average_rating must be calculated directly from overall review star ratings,
          NOT as the average of criteria averages.
        - Star distribution count and percentages must sum correctly.
        - Criteria averages must be accurately computed per criterion.
        """
        # Customer 1 review: overall = 4, cleanliness = 5, pricing = 3
        rev1 = Review.objects.create(
            shop=self.shop_general,
            user=self.customer1,
            order=self.order_completed,
            rating=4,
            comment="Review 1"
        )
        ReviewCriterionRating.objects.create(
            review=rev1, criterion_slug="cleanliness", criterion_name="Cleanliness", rating=5
        )
        ReviewCriterionRating.objects.create(
            review=rev1, criterion_slug="pricing", criterion_name="Pricing", rating=3
        )

        # Customer 2 completes order and posts review: overall = 5, cleanliness = 5, pricing = 4
        self.order_pending.status = Order.Status.COMPLETED
        self.order_pending.save()

        rev2 = Review.objects.create(
            shop=self.shop_general,
            user=self.customer2,
            order=self.order_pending,
            rating=5,
            comment="Review 2"
        )
        ReviewCriterionRating.objects.create(
            review=rev2, criterion_slug="cleanliness", criterion_name="Cleanliness", rating=5
        )
        ReviewCriterionRating.objects.create(
            review=rev2, criterion_slug="pricing", criterion_name="Pricing", rating=4
        )

        summary = self.shop_general.get_rating_summary()

        # Overall average: (4 + 5) / 2 = 4.5
        self.assertEqual(summary['overall_average_rating'], 4.5)
        self.assertEqual(summary['verified_reviews_count'], 2)

        # Star distribution: 1 five-star (50%), 1 four-star (50%)
        dist = summary['star_distribution']
        self.assertEqual(dist['5']['count'], 1)
        self.assertEqual(dist['5']['percentage'], 50.0)
        self.assertEqual(dist['4']['count'], 1)
        self.assertEqual(dist['4']['percentage'], 50.0)
        self.assertEqual(dist['3']['count'], 0)

        # Criteria averages:
        # cleanliness: (5 + 5) / 2 = 5.0
        # pricing: (3 + 4) / 2 = 3.5
        crit_map = {c['slug']: c['average'] for c in summary['criteria_averages']}
        self.assertEqual(crit_map['cleanliness'], 5.0)
        self.assertEqual(crit_map['pricing'], 3.5)

        # Test REST API rating-summary endpoint
        api_res = self.api_client.get(f"/api/v1/shops/shops/{self.shop_general.id}/rating-summary/")
        self.assertEqual(api_res.status_code, status.HTTP_200_OK)
        self.assertEqual(api_res.data['overall_average_rating'], 4.5)

    def test_future_category_support_admin_criteria_addition(self):
        """
        Admins can configure custom rating criteria per category via RatingCriterion model
        without code changes. Older reviews preserve snapshot data if criteria change.
        """
        # Admin creates a new custom criterion for general shops
        custom_crit = RatingCriterion.objects.create(
            category=self.cat_general,
            name="Packaging Eco-friendliness",
            name_ml="പരിസ്ഥിതി സൗഹൃദ പാക്കിംഗ്",
            slug="packaging_eco",
            is_active=True,
            order=10
        )

        # Criteria list for general shops now includes the new custom criterion
        criteria = self.shop_general.get_rating_criteria()
        slugs = [c['slug'] for c in criteria]
        self.assertIn("packaging_eco", slugs)

        # Customer submits review including the new criterion
        rev = Review.objects.create(
            shop=self.shop_general,
            user=self.customer1,
            order=self.order_completed,
            rating=5,
            comment="Great eco bags!"
        )
        rcr = ReviewCriterionRating.objects.create(
            review=rev,
            criterion=custom_crit,
            criterion_name=custom_crit.name,
            criterion_name_ml=custom_crit.name_ml,
            criterion_slug=custom_crit.slug,
            rating=5,
            feedback="Used paper bags!"
        )

        # Admin deactivates or deletes the criterion in the future
        custom_crit.is_active = False
        custom_crit.save()

        # The historical review preserves its snapshot data and rating fidelity
        rcr.refresh_from_db()
        self.assertEqual(rcr.criterion_name, "Packaging Eco-friendliness")
        self.assertEqual(rcr.criterion_slug, "packaging_eco")
        self.assertEqual(rcr.rating, 5)

    def test_web_portal_review_submission_view(self):
        """
        Tests the web view /shops/<shop_id>/review/ for HTML form submissions.
        """
        self.web_client.force_login(self.customer1)
        url = reverse('shop-submit-review', args=[self.shop_general.id])
        post_data = {
            'rating': '5',
            'comment': 'Exceptional service and quick delivery from web portal!',
            'order_id': str(self.order_completed.id),
            'criteria_cleanliness': '5',
            'feedback_cleanliness': 'Very clean',
            'criteria_pricing': '4',
            'feedback_pricing': 'Good prices',
            'criteria_quality': '5',
            'criteria_service': '5'
        }
        res = self.web_client.post(url, post_data)
        # Should redirect back to shop detail page
        self.assertEqual(res.status_code, 302)
        self.assertIn(f"/shops/{self.shop_general.id}/", res.url)

        # Verify review created
        rev = Review.objects.filter(shop=self.shop_general, user=self.customer1).first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.rating, 5)
        self.assertTrue(rev.is_verified_buyer)
        self.assertEqual(rev.criterion_ratings.count(), 4)












