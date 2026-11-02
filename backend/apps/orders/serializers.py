from django.db import transaction
from rest_framework import serializers
from .models import Order, OrderItem, Booking, ServiceRequest, Cart, CartItem
from apps.shops.models import Shop, Product

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price', 'subtotal']
        read_only_fields = ['id', 'product_name', 'unit_price', 'subtotal']

class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_phone = serializers.CharField(source='shop.contact_phone', read_only=True)
    shop_whatsapp = serializers.CharField(source='shop.whatsapp_number', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_phone',
            'shop',
            'shop_name',
            'shop_phone',
            'shop_whatsapp',
            'status',
            'delivery_type',
            'delivery_address',
            'notes',
            'checkout_group_id',
            'total_amount',
            'items',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'customer_phone', 'status', 'checkout_group_id', 'total_amount', 'created_at', 'updated_at']

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    shop_id = serializers.IntegerField(source='product.shop.id', read_only=True)
    shop_name = serializers.CharField(source='product.shop.name', read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_available = serializers.BooleanField(source='product.is_available', read_only=True)
    requires_prescription = serializers.BooleanField(source='product.requires_prescription', read_only=True)
    unit = serializers.CharField(source='product.unit', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id',
            'product',
            'product_name',
            'shop_id',
            'shop_name',
            'quantity',
            'unit_price',
            'subtotal',
            'unit',
            'is_available',
            'requires_prescription',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    grouped_by_shop = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'customer',
            'total_items',
            'total_amount',
            'items',
            'grouped_by_shop',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'created_at', 'updated_at']

    def get_grouped_by_shop(self, obj):
        grouped = obj.get_items_grouped_by_shop()
        serialized = []
        for g in grouped:
            serialized.append({
                'shop_id': g['shop'].id,
                'shop_name': g['shop'].name,
                'shop_phone': g['shop'].contact_phone,
                'is_open': g['is_open'],
                'subtotal': str(g['subtotal']),
                'has_prescription': g['has_prescription'],
                'items': CartItemSerializer(g['items'], many=True).data
            })
        return serialized

class CartAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

class CartUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)

class CartCheckoutSerializer(serializers.Serializer):
    delivery_type = serializers.ChoiceField(
        choices=Order.DeliveryType.choices,
        default=Order.DeliveryType.STORE_PICKUP
    )
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

class OrderCreateSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField()
    delivery_type = serializers.ChoiceField(choices=Order.DeliveryType.choices, default=Order.DeliveryType.STORE_PICKUP)
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemCreateSerializer(many=True)

    def create(self, validated_data):
        customer = self.context['request'].user
        items_data = validated_data.pop('items')
        shop_id = validated_data.pop('shop_id')

        if not items_data:
            raise serializers.ValidationError("Order must have at least one item.")

        shop = Shop.objects.filter(id=shop_id).first()
        if not shop:
            raise serializers.ValidationError({"shop_id": "Shop does not exist."})

        if shop.owner == customer:
            raise serializers.ValidationError({"shop_id": "You cannot place an order at your own shop."})

        if not shop.is_open:
            raise serializers.ValidationError({"shop_id": f"'{shop.name}' is currently closed. Cannot place order."})

        with transaction.atomic():
            total_amount = 0
            order = Order.objects.create(
                customer=customer,
                customer_phone=customer.phone_number,
                shop=shop,
                total_amount=0,
                **validated_data
            )

            for item_info in items_data:
                product_id = item_info['product_id']
                try:
                    product = Product.objects.get(id=product_id, shop=shop)
                except Product.DoesNotExist:
                    raise serializers.ValidationError({
                        "items": f"Product #{product_id} does not exist in shop '{shop.name}'."
                    })

                if not product.is_available:
                    raise serializers.ValidationError({
                        "items": f"Product '{product.name}' is currently out of stock."
                    })

                price = product.discount_price if product.discount_price else product.price
                subtotal = price * item_info['quantity']
                total_amount += subtotal

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    quantity=item_info['quantity'],
                    unit_price=price,
                    subtotal=subtotal
                )

            order.total_amount = total_amount
            order.save(update_fields=['total_amount'])
            return order

class BookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_phone',
            'shop',
            'shop_name',
            'service',
            'service_name',
            'booking_date',
            'time_slot',
            'number_of_people',
            'status',
            'special_notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'customer_phone', 'status', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            shop = attrs.get('shop')
            if shop and shop.owner == request.user:
                raise serializers.ValidationError({"shop": "You cannot book an appointment at your own shop."})
        return attrs

class ServiceRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_phone',
            'shop',
            'shop_name',
            'request_type',
            'description',
            'attachment',
            'expected_date',
            'status',
            'shop_response',
            'quoted_price',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'customer_phone', 'status', 'shop_response', 'quoted_price', 'created_at', 'updated_at']
