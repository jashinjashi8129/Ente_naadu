from django.db import models
from django.conf import settings
from apps.shops.models import Shop, Product

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'ഓർഡർ ലഭിച്ചു (Pending)'
        ACCEPTED = 'accepted', 'കടക്കാരൻ സ്വീകരിച്ചു (Accepted)'
        PREPARING = 'preparing', 'തയ്യാറാക്കുന്നു (Preparing)'
        READY = 'ready', 'വാങ്ങാൻ തയ്യാറായി (Ready for Pickup)'
        COMPLETED = 'completed', 'പൂർത്തിയായി (Completed)'
        CANCELLED = 'cancelled', 'റദ്ദാക്കി (Cancelled)'

    class DeliveryType(models.TextChoices):
        STORE_PICKUP = 'pickup', 'കടയിൽ വന്ന് വാങ്ങൽ (Store Pickup)'
        HOME_DELIVERY = 'delivery', 'ഹോം ഡെലിവറി (Home Delivery)'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="ഉപഭോക്താവ് (Customer)"
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="സ്ഥാപനം (Shop)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="സ്റ്റാറ്റസ് (Status)"
    )
    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices,
        default=DeliveryType.STORE_PICKUP,
        verbose_name="വാങ്ങുന്ന രീതി (Delivery Type)"
    )
    delivery_address = models.TextField(blank=True, verbose_name="ഡെലിവറി വിലാസം")
    customer_phone = models.CharField(max_length=17, verbose_name="കസ്റ്റമർ ഫോൺ")
    notes = models.TextField(blank=True, verbose_name="പ്രത്യേക നിർദ്ദേശങ്ങൾ (Notes)")
    checkout_group_id = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name="ചെക്ക്ഔട്ട് ഗ്രൂപ്പ് ഐഡി (Checkout Group ID)"
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="ആകെ തുക")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ഓർഡർ (Order)"
        verbose_name_plural = "ഓർഡറുകൾ (Orders)"
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.shop.name} ({self.get_status_display()})"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="ഓർഡർ"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="ഉൽപ്പന്നം"
    )
    product_name = models.CharField(max_length=200, verbose_name="ഉൽപ്പന്നത്തിന്റെ പേര്")
    quantity = models.PositiveIntegerField(default=1, verbose_name="എണ്ണം / അളവ്")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="വില")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="ആകെ")

    class Meta:
        verbose_name = "ഓർഡർ ഐറ്റം (Order Item)"
        verbose_name_plural = "ഓർഡർ ഐറ്റങ്ങൾ (Order Items)"

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

class Cart(models.Model):
    """
    Customer shopping cart for multi-product and multi-shop purchases.
    """
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        verbose_name="ഉപഭോക്താവ് (Customer)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ഷോപ്പിംഗ് കാർട്ട് (Shopping Cart)"
        verbose_name_plural = "ഷോപ്പിംഗ് കാർട്ടുകൾ (Shopping Carts)"

    def __str__(self):
        return f"Cart of {self.customer.full_name or self.customer.phone_number}"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items.all())

    def get_items_grouped_by_shop(self):
        """
        Organizes cart items grouped by shop with subtotals and prescription checks.
        """
        from collections import defaultdict
        grouped = defaultdict(list)
        for item in self.items.select_related('product', 'product__shop', 'product__shop__owner').all():
            grouped[item.product.shop].append(item)

        result = []
        for shop, items in grouped.items():
            shop_subtotal = sum(i.subtotal for i in items)
            has_prescription = any(getattr(i.product, 'requires_prescription', False) for i in items)
            result.append({
                'shop': shop,
                'items': items,
                'subtotal': shop_subtotal,
                'has_prescription': has_prescription,
                'is_open': shop.is_open,
            })
        return result

class CartItem(models.Model):
    """
    Individual item inside a customer's cart.
    Unique per (cart, product) to avoid duplicate lines.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="കാർട്ട്"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
        verbose_name="ഉൽപ്പന്നം"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="എണ്ണം")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "കാർട്ട് ഐറ്റം (Cart Item)"
        verbose_name_plural = "കാർട്ട് ഐറ്റങ്ങൾ (Cart Items)"
        unique_together = ('cart', 'product')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def unit_price(self):
        """Dynamic unit price directly from product model (tamper-proof)."""
        return self.product.discount_price if self.product.discount_price else self.product.price

    @property
    def subtotal(self):
        """Computed item subtotal."""
        return self.unit_price * self.quantity

class Booking(models.Model):
    """
    Time-slot Booking for Barbers, Akshaya Centers, and Restaurant Tables.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'ബുക്കിംഗ് കാത്തിരിക്കുന്നു (Pending)'
        CONFIRMED = 'confirmed', 'സ്ഥിരീകരിച്ചു (Confirmed)'
        COMPLETED = 'completed', 'പൂർത്തിയായി (Completed)'
        CANCELLED = 'cancelled', 'റദ്ദാക്കി (Cancelled)'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="ഉപഭോക്താവ്"
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="സ്ഥാപനം"
    )
    service = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        verbose_name="ആവശ്യമായ സേവനം"
    )
    booking_date = models.DateField(verbose_name="തീയതി (Booking Date)")
    time_slot = models.CharField(max_length=50, verbose_name="സമയ സ്ലോട്ട് (e.g. 10:00 AM - 10:30 AM)")
    number_of_people = models.PositiveSmallIntegerField(default=1, verbose_name="ആളുകളുടെ എണ്ണം")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="സ്റ്റാറ്റസ്"
    )
    customer_phone = models.CharField(max_length=17, verbose_name="ഫോൺ നമ്പർ")
    special_notes = models.TextField(blank=True, verbose_name="പ്രത്യേക ആവശ്യങ്ങൾ")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ബുക്കിംഗ് (Booking)"
        verbose_name_plural = "ബുക്കിംഗുകൾ (Bookings)"
        ordering = ['-booking_date', '-created_at']

    def __str__(self):
        return f"Booking #{self.id} - {self.shop.name} ({self.booking_date} {self.time_slot})"

class ServiceRequest(models.Model):
    """
    Inquiry & Custom Requests (Tailoring with measurements/photos, Medical prescription check).
    Prescription drugs are checked by pharmacist; not directly purchased without verification.
    """
    class RequestType(models.TextChoices):
        PRESCRIPTION = 'prescription', 'മരുന്ന് കുറിപ്പടി അന്വേഷണം (Medical Prescription)'
        TAILORING = 'tailoring', 'തയ്യൽ / അളവ് അന്വേഷണം (Custom Tailoring)'
        GENERAL = 'general', 'മറ്റ് അന്വേഷണം (General Inquiry)'

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'സമർപ്പിച്ചു (Submitted)'
        IN_REVIEW = 'in_review', 'പരിശോധിക്കുന്നു (In Review)'
        ACCEPTED = 'accepted', 'ലഭ്യമാണ് / സ്വീകരിച്ചു (Accepted)'
        REJECTED = 'rejected', 'ലഭ്യമല്ല / നിരസിച്ചു (Unavailable)'
        COMPLETED = 'completed', 'പൂർത്തിയായി (Completed)'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='service_requests',
        verbose_name="ഉപഭോക്താവ്"
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='service_requests',
        verbose_name="സ്ഥാപനം"
    )
    request_type = models.CharField(
        max_length=30,
        choices=RequestType.choices,
        default=RequestType.GENERAL,
        verbose_name="അന്വേഷണ തരം"
    )
    description = models.TextField(verbose_name="വിശദാംശങ്ങൾ (കുറിപ്പടി വിവരങ്ങൾ / തയ്യൽ അളവുകൾ)")
    attachment = models.ImageField(upload_to='requests/attachments/', null=True, blank=True, verbose_name="ഫോട്ടോ / കുറിപ്പടി")
    customer_phone = models.CharField(max_length=17, verbose_name="കസ്റ്റമർ ഫോൺ")

    expected_date = models.DateField(null=True, blank=True, verbose_name="ആവശ്യപ്പെടുന്ന തീയതി")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        verbose_name="സ്റ്റാറ്റസ്"
    )
    shop_response = models.TextField(blank=True, verbose_name="കടയുടെ മറുപടി")
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="ഏകദേശ വില")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "സർവീസ് റിക്വസ്റ്റ് (Service Request)"
        verbose_name_plural = "സർവീസ് റിക്വസ്റ്റുകൾ (Service Requests)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_request_type_display()} - {self.shop.name} ({self.get_status_display()})"
