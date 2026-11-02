import uuid
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from .models import Order, OrderItem, Booking, ServiceRequest, Cart, CartItem
from apps.shops.models import Shop, Product
from apps.accounts.models import AuditLog
from apps.common.permissions import (
    IsOrderParticipant,
    IsBookingParticipant,
    IsServiceRequestParticipant
)
from apps.common.notifications import (
    notify_order_created,
    notify_order_status_changed,
    notify_booking_requested,
    notify_booking_status_changed
)
from apps.common.audit import log_audit
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    BookingSerializer,
    ServiceRequestSerializer,
    CartSerializer,
    CartItemSerializer,
    CartAddSerializer,
    CartUpdateSerializer,
    CartCheckoutSerializer
)

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrderParticipant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'super_admin':
            return Order.objects.all().prefetch_related('items', 'shop', 'customer')

        return Order.objects.filter(
            Q(customer=user) | Q(shop__owner=user)
        ).prefetch_related('items', 'shop', 'customer').distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # In-app notification to the shop owner
        notify_order_created(order)

        # Audit log entry
        log_audit(
            performed_by=request.user,
            action=AuditLog.Action.ORDER_STATUS_UPDATE,
            target_type='Order',
            target_id=order.id,
            target_identifier=f"Order #{order.id}",
            reason=f"Order placed with {order.shop.name} for ₹{order.total_amount}"
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        self.check_object_permissions(self.request, instance)
        if not user.is_staff and user.role != 'super_admin' and instance.shop.owner != user:
            raise PermissionDenied("You do not have permission to modify this order directly.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and user.role != 'super_admin':
            raise PermissionDenied("Orders cannot be deleted; they must be cancelled.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        order = self.get_object()
        self.check_object_permissions(request, order)
        user = request.user
        new_status = request.data.get('status')

        if not new_status or new_status not in Order.Status.values:
            return Response(
                {"error": f"Invalid status. Must be one of: {list(Order.Status.values)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.shop.owner != user and not user.is_staff and user.role != 'super_admin':
            if order.customer == user and new_status == Order.Status.CANCELLED and order.status == Order.Status.PENDING:
                order.status = Order.Status.CANCELLED
                order.save(update_fields=['status'])

                notify_order_status_changed(order)
                log_audit(
                    performed_by=user,
                    action=AuditLog.Action.ORDER_CANCEL,
                    target_type='Order',
                    target_id=order.id,
                    target_identifier=f"Order #{order.id}",
                    reason="Customer cancelled pending order"
                )
                return Response(OrderSerializer(order).data)
            raise PermissionDenied("Only the shop owner can update this order's status.")

        order.status = new_status
        order.save(update_fields=['status'])

        notify_order_status_changed(order)
        log_audit(
            performed_by=user,
            action=AuditLog.Action.ORDER_STATUS_UPDATE,
            target_type='Order',
            target_id=order.id,
            target_identifier=f"Order #{order.id}",
            reason=f"Status updated to {new_status}"
        )
        return Response(OrderSerializer(order).data)

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookingParticipant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'super_admin':
            return Booking.objects.all().select_related('shop', 'customer', 'service')

        return Booking.objects.filter(
            Q(customer=user) | Q(shop__owner=user)
        ).select_related('shop', 'customer', 'service')

    def perform_create(self, serializer):
        user = self.request.user
        booking = serializer.save(customer=user, customer_phone=user.phone_number)

        # Notify business owner
        notify_booking_requested(booking)

        log_audit(
            performed_by=user,
            action=AuditLog.Action.BOOKING_STATUS_UPDATE,
            target_type='Booking',
            target_id=booking.id,
            target_identifier=f"Booking #{booking.id}",
            reason=f"New appointment requested for {booking.booking_date} ({booking.time_slot})"
        )

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        self.check_object_permissions(self.request, instance)
        if not user.is_staff and user.role != 'super_admin' and instance.shop.owner != user:
            raise PermissionDenied("You do not have permission to modify this booking directly.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and user.role != 'super_admin':
            raise PermissionDenied("Bookings cannot be deleted; update status to cancelled.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        booking = self.get_object()
        self.check_object_permissions(request, booking)
        user = request.user
        new_status = request.data.get('status')

        if not new_status or new_status not in Booking.Status.values:
            return Response({"error": "Invalid booking status"}, status=status.HTTP_400_BAD_REQUEST)

        if booking.shop.owner != user and not user.is_staff and user.role != 'super_admin':
            if booking.customer == user and new_status == Booking.Status.CANCELLED:
                if booking.status != Booking.Status.PENDING:
                    return Response({
                        "error": "സ്ഥാപനം സ്ഥിരീകരിച്ച (Approved) അപ്പോയിന്റ്മെന്റുകൾ നേരിട്ട് ക്യാൻസൽ ചെയ്യാൻ കഴിയില്ല. ദയവായി കടയുമായി ഫോണിൽ ബന്ധപ്പെടുക."
                    }, status=status.HTTP_400_BAD_REQUEST)

                booking.status = Booking.Status.CANCELLED
                booking.save(update_fields=['status'])

                notify_booking_status_changed(booking, performed_by=user)
                log_audit(
                    performed_by=user,
                    action=AuditLog.Action.BOOKING_CANCEL,
                    target_type='Booking',
                    target_id=booking.id,
                    target_identifier=f"Booking #{booking.id}",
                    reason="Customer cancelled pending appointment"
                )
                return Response(BookingSerializer(booking).data)
            raise PermissionDenied("Only the shop owner can confirm/update booking.")

        booking.status = new_status
        booking.save(update_fields=['status'])

        notify_booking_status_changed(booking, performed_by=user)
        log_audit(
            performed_by=user,
            action=AuditLog.Action.BOOKING_STATUS_UPDATE,
            target_type='Booking',
            target_id=booking.id,
            target_identifier=f"Booking #{booking.id}",
            reason=f"Shop owner updated appointment status to {new_status}"
        )
        return Response(BookingSerializer(booking).data)

class ServiceRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsServiceRequestParticipant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'super_admin':
            return ServiceRequest.objects.all().select_related('shop', 'customer')

        return ServiceRequest.objects.filter(
            Q(customer=user) | Q(shop__owner=user)
        ).select_related('shop', 'customer')

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(customer=user, customer_phone=user.phone_number)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if not user.is_staff and user.role != 'super_admin' and instance.shop.owner != user:
            raise PermissionDenied("You do not have permission to modify this service request directly.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and user.role != 'super_admin':
            raise PermissionDenied("Service requests cannot be deleted.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='respond')
    def respond_to_request(self, request, pk=None):
        req_obj = self.get_object()
        user = request.user

        if req_obj.shop.owner != user and not user.is_staff and user.role != 'super_admin':
            raise PermissionDenied("Only the shop owner can respond to service requests.")

        new_status = request.data.get('status')
        shop_response = request.data.get('response', '')
        quoted_price = request.data.get('quoted_price')

        if new_status and new_status in ServiceRequest.Status.values:
            req_obj.status = new_status
        if shop_response:
            req_obj.shop_response = shop_response
        if quoted_price is not None:
            req_obj.quoted_price = quoted_price

        req_obj.save()
        return Response(ServiceRequestSerializer(req_obj).data)


class CartViewSet(viewsets.ViewSet):
    """
    API ViewSet for managing the authenticated customer's shopping cart:
    - View cart (GET /api/v1/orders/cart/)
    - Add product to cart (POST /api/v1/orders/cart/add/)
    - Update item quantity (PATCH /api/v1/orders/cart/items/<id>/)
    - Remove item (DELETE /api/v1/orders/cart/items/<id>/delete/)
    - Clear cart (POST /api/v1/orders/cart/clear/)
    - Multi-shop checkout (POST /api/v1/orders/cart/checkout/)
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_cart(self, user):
        cart, _ = Cart.objects.get_or_create(customer=user)
        return cart

    def list(self, request):
        cart = self._get_cart(request.user)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'], url_path='add')
    def add_item(self, request):
        serializer = CartAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data.get('quantity', 1)

        product = get_object_or_404(Product, id=product_id)
        if product.shop.owner == request.user:
            return Response(
                {"error": "നിങ്ങളുടെ സ്വന്തം കടയിലെ സാധനങ്ങൾ കാർട്ടിലേക്ക് ചേർക്കാൻ കഴിയില്ല."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not product.is_available:
            return Response(
                {"error": f"'{product.name}' നിലവിൽ ലഭ്യമല്ല (Out of stock)."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not product.shop.is_open:
            return Response(
                {"error": f"'{product.shop.name}' ഇപ്പോൾ അടച്ചിരിക്കുകയാണ് (Shop closed)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = self._get_cart(request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity', 'updated_at'])

        cart.refresh_from_db()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch', 'post'], url_path=r'items/(?P<item_id>\d+)')
    def update_item(self, request, item_id=None):
        cart = self._get_cart(request.user)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)

        serializer = CartUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_quantity = serializer.validated_data['quantity']

        if new_quantity <= 0:
            item.delete()
        else:
            item.quantity = new_quantity
            item.save(update_fields=['quantity', 'updated_at'])

        cart.refresh_from_db()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete', 'post'], url_path=r'items/(?P<item_id>\d+)/delete')
    def delete_item(self, request, item_id=None):
        cart = self._get_cart(request.user)
        item = get_object_or_404(CartItem, id=item_id, cart=cart)
        item.delete()
        cart.refresh_from_db()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='clear')
    def clear(self, request):
        cart = self._get_cart(request.user)
        cart.items.all().delete()
        cart.refresh_from_db()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='checkout')
    def checkout(self, request):
        cart = self._get_cart(request.user)
        if not cart.items.exists():
            return Response(
                {"error": "ഷോപ്പിംഗ് കാർട്ട് കാലിയാണ് (Your cart is empty)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CartCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        delivery_type = serializer.validated_data.get('delivery_type', Order.DeliveryType.STORE_PICKUP)
        delivery_address = serializer.validated_data.get('delivery_address', '')
        customer_phone = serializer.validated_data.get('customer_phone') or request.user.phone_number
        notes = serializer.validated_data.get('notes', '')

        grouped_shops = cart.get_items_grouped_by_shop()
        if not grouped_shops:
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Immediate pre-checkout validation for product availability & shop status
        for group in grouped_shops:
            shop = group['shop']
            if not shop.is_open:
                return Response(
                    {"error": f"'{shop.name}' ഇപ്പോൾ അടച്ചിരിക്കുകയാണ്. ഓർഡർ ചെയ്യാൻ സാധ്യമല്ല."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            for item in group['items']:
                if not item.product.is_available:
                    return Response(
                        {"error": f"'{item.product.name}' നിലവിൽ ലഭ്യമല്ല."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        checkout_group_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        created_orders = []

        with transaction.atomic():
            for group in grouped_shops:
                shop = group['shop']
                items = group['items']
                shop_total = Decimal('0.00')

                order = Order.objects.create(
                    customer=request.user,
                    shop=shop,
                    status=Order.Status.PENDING,
                    delivery_type=delivery_type,
                    delivery_address=delivery_address.strip() if delivery_address else '',
                    customer_phone=customer_phone.strip() if customer_phone else request.user.phone_number,
                    notes=notes.strip() if notes else '',
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

            # Successfully created all shop orders -> clear cart items
            cart.items.all().delete()

        # Notify shop owners and create audit entries for each generated order
        for order in created_orders:
            notify_order_created(order)
            log_audit(
                performed_by=request.user,
                action=AuditLog.Action.ORDER_STATUS_UPDATE,
                target_type='Order',
                target_id=order.id,
                target_identifier=f"Order #{order.id}",
                reason=f"Multi-cart checkout order placed with {order.shop.name} for ₹{order.total_amount}"
            )

        serialized_orders = OrderSerializer(created_orders, many=True).data
        return Response({
            "message": f"{len(created_orders)} കടകളിലേക്കായി ഓർഡറുകൾ വിജയകരമായി സമർപ്പിച്ചു.",
            "checkout_group_id": checkout_group_id,
            "orders": serialized_orders
        }, status=status.HTTP_201_CREATED)

