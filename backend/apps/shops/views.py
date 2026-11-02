from django.db import models
from rest_framework import viewsets, permissions, filters, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import (
    ShopCategory,
    Shop,
    Product,
    Review,
    RatingCriterion,
    ReviewCriterionRating
)
from .serializers import (
    ShopCategorySerializer,
    ShopSerializer,
    ProductSerializer,
    ReviewSerializer,
    RatingCriterionSerializer,
    ReviewCriterionRatingSerializer,
    PublicShopRegisterSerializer
)
from .services import ShopProgressCalculator
from apps.accounts.models import User, AuditLog
from apps.orders.models import Order, OrderItem, Booking
from apps.common.geo import is_valid_coord, haversine_distance, get_bounding_box
from apps.common.permissions import IsShopOwner, IsOwnerOrReadOnly
from apps.common.audit import log_audit

class ShopCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShopCategory.objects.all()
    serializer_class = ShopCategorySerializer
    permission_classes = [permissions.AllowAny]

class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all().select_related('category', 'owner')
    serializer_class = ShopSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'address', 'category__name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Public users only see verified shops; owners see their own; admins see all
        if not user.is_authenticated or (user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN] and not user.is_staff):
            if user.is_authenticated and user.role == User.Role.SHOP_OWNER:
                qs = qs.filter(models.Q(is_verified=True) | models.Q(owner=user))
            else:
                qs = qs.filter(is_verified=True)

        ward = self.request.query_params.get('ward')
        area_id = self.request.query_params.get('area')
        category_id = self.request.query_params.get('category')
        interaction_mode = self.request.query_params.get('mode')
        is_open = self.request.query_params.get('is_open')

        if ward:
            qs = qs.filter(ward_number=ward)
        if area_id:
            qs = qs.filter(area_id=area_id)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if interaction_mode:
            qs = qs.filter(category__interaction_mode=interaction_mode)
        if is_open is not None:
            qs = qs.filter(is_open=is_open.lower() in ('true', '1'))
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != User.Role.SHOP_OWNER and user.role != User.Role.SUPER_ADMIN:
            user.role = User.Role.SHOP_OWNER
            user.save(update_fields=['role'])
        serializer.save(owner=user, is_verified=user.is_staff or user.role == User.Role.SUPER_ADMIN)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You do not have permission to edit this shop.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You do not have permission to delete this shop.")
        instance.delete()

    @action(detail=True, methods=['post'], url_path='toggle-open')
    def toggle_open(self, request, pk=None):
        shop = self.get_object()
        if shop.owner != request.user and not request.user.is_staff and request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("Only the shop owner can toggle open/closed status.")
        shop.is_open = not shop.is_open
        shop.save(update_fields=['is_open'])
        return Response({"status": "updated", "is_open": shop.is_open})

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_shop(self, request, pk=None):
        if not request.user.is_staff and request.user.role not in [User.Role.SUPER_ADMIN, User.Role.WARD_ADMIN]:
            raise PermissionDenied("Admin permission required to approve shops.")
        shop = self.get_object()
        shop.is_verified = True
        shop.save(update_fields=['is_verified'])

        # Audit log
        AuditLog.objects.create(
            performed_by=request.user,
            action=AuditLog.Action.APPROVE_SHOP,
            target_type='Shop',
            target_id=shop.id,
            target_identifier=shop.name,
            reason="Verified and approved shop credentials"
        )
        return Response({"message": f"Shop {shop.name} verified and approved successfully."})

    @action(detail=False, methods=['get'], url_path='nearby', permission_classes=[permissions.AllowAny])
    def nearby_shops(self, request):
        """
        Discovers verified, active shops near a given GPS location.
        Filters by radius, category, and search query.
        Calculates Haversine distance and sorts closest first.
        If coordinates are omitted or unavailable, returns all verified shops
        with valid coordinates without distance filtering.
        """
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = request.query_params.get('radius', '10')

        has_user_coords = False
        if lat is not None and lng is not None:
            if not is_valid_coord(lat, lng):
                return Response({"error": "Invalid GPS coordinates."}, status=status.HTTP_400_BAD_REQUEST)
            lat = float(lat)
            lng = float(lng)
            has_user_coords = True
        elif request.user.is_authenticated:
            user_loc = getattr(request.user, 'location', None)
            if user_loc and user_loc.latitude and user_loc.longitude and is_valid_coord(user_loc.latitude, user_loc.longitude):
                lat = float(user_loc.latitude)
                lng = float(user_loc.longitude)
                has_user_coords = True

        try:
            radius_km = float(radius)
            if radius_km <= 0 or radius_km > 100:
                radius_km = 10.0
        except (ValueError, TypeError):
            radius_km = 10.0

        qs = Shop.objects.filter(
            is_verified=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('category', 'area')

        category_id = request.query_params.get('category')
        if category_id and category_id.isdigit():
            qs = qs.filter(category_id=int(category_id))

        search_q = request.query_params.get('search', '').strip()
        if search_q:
            qs = qs.filter(
                models.Q(name__icontains=search_q) |
                models.Q(description__icontains=search_q) |
                models.Q(address__icontains=search_q)
            )

        if has_user_coords:
            bbox = get_bounding_box(lat, lng, radius_km)
            if bbox:
                qs = qs.filter(
                    latitude__gte=bbox['min_lat'],
                    latitude__lte=bbox['max_lat'],
                    longitude__gte=bbox['min_lon'],
                    longitude__lte=bbox['max_lon']
                )

        results = []
        for shop in qs[:150]:
            dist = None
            if has_user_coords:
                dist = haversine_distance(lat, lng, shop.latitude, shop.longitude)
                if dist is None or dist > radius_km:
                    continue

            results.append({
                "id": shop.id,
                "name": shop.name,
                "category_id": shop.category_id,
                "category_name": shop.category.name if shop.category else "ജനറൽ",
                "business_type": shop.business_type,
                "address": shop.address,
                "ward_number": shop.ward_number,
                "area_name": shop.area.name if shop.area else "",
                "contact_phone": shop.contact_phone,
                "whatsapp_number": shop.whatsapp_number,
                "is_open": shop.is_open,
                "todays_offer": shop.todays_offer,
                "latitude": float(shop.latitude),
                "longitude": float(shop.longitude),
                "distance_km": dist,
                "banner_url": shop.banner_image.url if shop.banner_image else None,
                "detail_url": f"/shops/{shop.id}/",
                "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={shop.latitude},{shop.longitude}"
            })

        if has_user_coords:
            results.sort(key=lambda s: s['distance_km'])
        else:
            results.sort(key=lambda s: (not s['is_open'], s['name']))

        return Response({
            "user_lat": float(lat) if has_user_coords else None,
            "user_lng": float(lng) if has_user_coords else None,
            "has_user_location": has_user_coords,
            "radius_km": radius_km if has_user_coords else None,
            "count": len(results),
            "shops": results
        })

    def nearby(self, request):
        """Alias for nearby_shops."""
        return self.nearby_shops(request)

    @action(detail=True, methods=['post'], url_path='location')
    def update_location(self, request, pk=None):
        """
        Updates a shop's physical GPS location.
        Only the shop owner or admin can update this shop's location.
        """
        shop = self.get_object()
        user = request.user

        if shop.owner != user and not user.is_staff and user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("നിങ്ങൾക്ക് ഈ കടയുടെ ലൊക്കേഷൻ മാറ്റാൻ അനുവാദമില്ല.")

        lat = request.data.get('latitude')
        lng = request.data.get('longitude')

        if not is_valid_coord(lat, lng):
            return Response(
                {"error": "Invalid coordinates. Latitude must be between -90 and 90, Longitude between -180 and 180."},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop.latitude = lat
        shop.longitude = lng
        shop.save(update_fields=['latitude', 'longitude', 'updated_at'])

        return Response({
            "message": f"'{shop.name}'-ന്റെ ലൊക്കേഷൻ വിജയകരമായി രേഖപ്പെടുത്തി.",
            "latitude": float(shop.latitude),
            "longitude": float(shop.longitude)
        })

    def location(self, request, pk=None):
        """Alias for update_location."""
        return self.update_location(request, pk)

    @action(detail=True, methods=['get'], url_path='progress', permission_classes=[permissions.IsAuthenticated])
    def shop_progress(self, request, pk=None):
        """
        Progress tracking endpoint for an individual shop.
        Enforces strict object-level privacy:
        - Only the shop owner or Super Admin can view this shop's progress.
        - Other shop owners or citizens receive 403 Forbidden.
        - Customer private information is never included in the payload.
        """
        shop = self.get_object()
        user = request.user

        is_owner = (shop.owner_id == user.id)
        is_admin = (user.is_staff or user.role == User.Role.SUPER_ADMIN)

        if not (is_owner or is_admin):
            raise PermissionDenied("മറ്റൊരു കടയുടെ പുരോഗതി വിവരങ്ങൾ കാണാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.")

        progress_data = shop.get_progress()
        return Response(progress_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='admin-progress', permission_classes=[permissions.IsAuthenticated])
    def admin_progress_overview(self, request):
        """
        Admin progress dashboard summary endpoint across all registered shops.
        Protected: Only accessible by Super Admin / Staff.
        Supports search, category, ward, and verification filtering.
        """
        user = request.user
        if not (user.is_staff or user.role == User.Role.SUPER_ADMIN):
            raise PermissionDenied("അഡ്മിന്മാർക്ക് മാത്രമേ എല്ലാ കടകളുടെയും പുരോഗതി വിവരങ്ങൾ കാണാൻ അനുമതിയുള്ളൂ.")

        qs = Shop.objects.all().select_related('category', 'owner', 'area')

        # Filters
        search_q = request.query_params.get('search', '').strip()
        if search_q:
            qs = qs.filter(
                models.Q(name__icontains=search_q) |
                models.Q(owner__full_name__icontains=search_q) |
                models.Q(owner__phone_number__icontains=search_q) |
                models.Q(contact_phone__icontains=search_q)
            )

        category_id = request.query_params.get('category')
        if category_id and category_id.isdigit():
            qs = qs.filter(category_id=int(category_id))

        ward = request.query_params.get('ward')
        if ward and ward.isdigit():
            qs = qs.filter(ward_number=int(ward))

        is_verified = request.query_params.get('is_verified')
        if is_verified is not None:
            qs = qs.filter(is_verified=is_verified.lower() in ('true', '1', 'yes'))

        summary = ShopProgressCalculator.get_admin_summary(qs)
        return Response(summary, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='rating-summary', permission_classes=[permissions.AllowAny])
    def rating_summary(self, request, pk=None):
        """
        Shop Rating Summary Endpoint:
        Returns overall average rating (from all valid reviews), total reviews,
        criteria-wise averages, star distribution (1-5), and recent reviews.
        """
        shop = self.get_object()
        return Response(shop.get_rating_summary(), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='rating-criteria', permission_classes=[permissions.AllowAny])
    def rating_criteria(self, request, pk=None):
        """
        Returns active rating criteria configured for this shop's category/business type.
        """
        shop = self.get_object()
        return Response(shop.get_rating_criteria(), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='can-review', permission_classes=[permissions.IsAuthenticated])
    def can_review(self, request, pk=None):
        """
        Validates if current authenticated user is eligible to rate/review this shop:
        - Must have at least 1 completed order or completed booking.
        - Must not have already reviewed this shop (duplicate prevention).
        - Must not be the shop owner.
        Returns candidate orders and bookings for review selection.
        """
        shop = self.get_object()
        user = request.user

        if shop.owner == user:
            return Response({
                "can_review": False,
                "reason": "Shop owners cannot review their own shop.",
                "reason_ml": "കടയുടമകൾക്ക് സ്വന്തം കടയ്ക്ക് റിവ്യൂ നൽകാൻ സാധിക്കില്ല."
            }, status=status.HTTP_200_OK)

        existing_review = Review.objects.filter(shop=shop, user=user).first()
        if existing_review:
            return Response({
                "can_review": False,
                "has_reviewed": True,
                "review_id": existing_review.id,
                "reason": "You have already reviewed this shop.",
                "reason_ml": "നിങ്ങൾ ഇതിനകം ഈ കടയ്ക്ക് റിവ്യൂ നൽകിയിട്ടുണ്ട്."
            }, status=status.HTTP_200_OK)

        # Completed orders not yet reviewed
        completed_orders = Order.objects.filter(
            customer=user,
            shop=shop,
            status=Order.Status.COMPLETED
        ).exclude(reviews__isnull=False).values('id', 'created_at', 'total_amount')

        # Completed bookings not yet reviewed
        completed_bookings = Booking.objects.filter(
            customer=user,
            shop=shop,
            status=Booking.Status.COMPLETED
        ).exclude(reviews__isnull=False).values('id', 'booking_date', 'time_slot', 'service__name')

        can_rate = completed_orders.exists() or completed_bookings.exists()
        return Response({
            "can_review": can_rate,
            "has_reviewed": False,
            "eligible_orders": list(completed_orders),
            "eligible_bookings": list(completed_bookings),
            "reason": None if can_rate else "Completed order or booking required to review this shop.",
            "reason_ml": None if can_rate else "റിവ്യൂ നൽകാൻ പൂർത്തിയായ ഓർഡറോ ബുക്കിംഗോ ആവശ്യമാണ്."
        }, status=status.HTTP_200_OK)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().select_related('shop')
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsShopOwner()]

    def get_queryset(self):
        qs = super().get_queryset()
        shop_id = self.request.query_params.get('shop')
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        return qs

    def perform_create(self, serializer):
        shop = serializer.validated_data.get('shop')
        if shop.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only add products to your own shop.")
        product = serializer.save()
        log_audit(
            performed_by=self.request.user,
            action=AuditLog.Action.PRODUCT_CREATE,
            target_type='Product',
            target_id=product.id,
            target_identifier=product.name,
            reason=f"Added to shop {shop.name} (#{shop.id})"
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        self.check_object_permissions(self.request, instance)
        if instance.shop.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only update products in your own shop.")

        # Prevent transferring product to another shop
        target_shop = serializer.validated_data.get('shop', instance.shop)
        if target_shop != instance.shop:
            if target_shop.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
                raise PermissionDenied("You cannot reassign product to a shop you do not own.")

        product = serializer.save()
        log_audit(
            performed_by=self.request.user,
            action=AuditLog.Action.PRODUCT_UPDATE,
            target_type='Product',
            target_id=product.id,
            target_identifier=product.name,
            reason=f"Updated product in shop {instance.shop.name}"
        )

    def perform_destroy(self, instance):
        self.check_object_permissions(self.request, instance)
        if instance.shop.owner != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete products from your own shop.")

        # Check if the product or service is linked to existing order items or bookings
        has_orders = OrderItem.objects.filter(product=instance).exists()
        has_bookings = Booking.objects.filter(service=instance).exists()

        if has_orders or has_bookings:
            # Soft-delete: mark unavailable to preserve historical order & booking records
            instance.is_available = False
            instance.save(update_fields=['is_available'])
            log_audit(
                performed_by=self.request.user,
                action=AuditLog.Action.PRODUCT_DELETE,
                target_type='Product',
                target_id=instance.id,
                target_identifier=instance.name,
                reason="Soft-deleted (marked unavailable) because product is linked to orders/bookings"
            )
        else:
            log_audit(
                performed_by=self.request.user,
                action=AuditLog.Action.PRODUCT_DELETE,
                target_type='Product',
                target_id=instance.id,
                target_identifier=instance.name,
                reason="Hard-deleted product (no associated order/booking records)"
            )
            instance.delete()

    @action(detail=True, methods=['post'], url_path='toggle-stock')
    def toggle_stock(self, request, pk=None):
        """
        Allows the shop owner to toggle product stock in/out of stock via API.
        """
        product = self.get_object()
        self.check_object_permissions(request, product)
        target_state = request.data.get('is_available')
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
        return Response({
            "status": "updated",
            "is_available": product.is_available,
            "product_id": product.id,
            "name": product.name
        })

class RatingCriterionViewSet(viewsets.ModelViewSet):
    """
    Rating Criteria Management Endpoint.
    Admin can configure, add, update, and disable criteria for any category or business type.
    Non-admin users can view active criteria.
    """
    queryset = RatingCriterion.objects.all().order_by('order', 'name')
    serializer_class = RatingCriterionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(is_active=True)

        category_id = self.request.query_params.get('category')
        if category_id and category_id.isdigit():
            qs = qs.filter(models.Q(category_id=int(category_id)) | models.Q(category__isnull=True))

        business_type = self.request.query_params.get('business_type')
        if business_type:
            qs = qs.filter(business_type=business_type)

        return qs


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all().select_related('user', 'shop', 'order', 'booking').prefetch_related('criterion_ratings')
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        shop_id = self.request.query_params.get('shop')
        if shop_id:
            return Review.objects.filter(shop_id=shop_id)
        return Review.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        shop = serializer.validated_data.get('shop')

        if shop.owner == user:
            raise PermissionDenied("Shop owners cannot review their own shop.")

        # Check if user already reviewed this shop (duplicate prevention)
        if Review.objects.filter(shop=shop, user=user).exists():
            raise ValidationError("You have already reviewed this shop.")

        # Check if verified buyer (has at least 1 completed order or completed booking)
        has_completed_order = Order.objects.filter(
            customer=user,
            shop=shop,
            status=Order.Status.COMPLETED
        ).exists()
        has_completed_booking = Booking.objects.filter(
            customer=user,
            shop=shop,
            status=Booking.Status.COMPLETED
        ).exists()

        if not (has_completed_order or has_completed_booking):
            raise ValidationError("You must have a completed order or booking with this shop to leave a review.")

        serializer.save(user=user, is_verified_buyer=True)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.user != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only edit your own reviews.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff and self.request.user.role != User.Role.SUPER_ADMIN:
            raise PermissionDenied("You can only delete your own reviews.")
        instance.delete()

    @action(detail=False, methods=['get'], url_path='my-review', permission_classes=[permissions.IsAuthenticated])
    def my_review(self, request):
        """
        Retrieves the authenticated user's review for a specific shop.
        Usage: GET /api/v1/shops/reviews/my-review/?shop=1
        """
        shop_id = request.query_params.get('shop')
        if not shop_id or not shop_id.isdigit():
            return Response({"error": "shop parameter is required and must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        review = Review.objects.filter(shop_id=int(shop_id), user=request.user).first()
        if not review:
            return Response({"has_reviewed": False, "review": None}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(review)
        return Response({"has_reviewed": True, "review": serializer.data}, status=status.HTTP_200_OK)


class PublicShopRegisterView(views.APIView):
    """
    Public 1-step registration for new shop owners.
    Creates User (role='shop_owner') and the Shop record in one atomic step.
    Returns auth token, user details, and shop details.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = PublicShopRegisterSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

