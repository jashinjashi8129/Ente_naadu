from rest_framework import serializers
from django.db import transaction
from django.db.models import Avg
from rest_framework.authtoken.models import Token
from apps.accounts.models import User, Area
from apps.orders.models import Order, Booking
from .models import (
    ShopCategory,
    Shop,
    Product,
    Review,
    ShopWorkingHour,
    RatingCriterion,
    ReviewCriterionRating
)

class ShopWorkingHourSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = ShopWorkingHour
        fields = ['id', 'day', 'day_display', 'opening_time', 'closing_time', 'is_closed']

class ShopCategorySerializer(serializers.ModelSerializer):
    shops_count = serializers.IntegerField(source='shops.count', read_only=True)
    interaction_mode_display = serializers.CharField(source='get_interaction_mode_display', read_only=True)

    class Meta:
        model = ShopCategory
        fields = ['id', 'name', 'description', 'icon_name', 'interaction_mode', 'interaction_mode_display', 'shops_count']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id',
            'shop',
            'name',
            'description',
            'price',
            'discount_price',
            'unit',
            'service_duration_minutes',
            'is_available',
            'image',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class RatingCriterionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)

    class Meta:
        model = RatingCriterion
        fields = [
            'id',
            'category',
            'category_name',
            'business_type',
            'business_type_display',
            'name',
            'name_ml',
            'slug',
            'description',
            'is_active',
            'order'
        ]


class ReviewCriterionRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewCriterionRating
        fields = [
            'id',
            'criterion',
            'criterion_name',
            'criterion_name_ml',
            'criterion_slug',
            'rating',
            'feedback',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    criterion_ratings = ReviewCriterionRatingSerializer(many=True, read_only=True)
    criteria_ratings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="List of criterion rating objects: [{'criterion_slug': 'food_quality', 'rating': 5, 'feedback': 'Delicious'}]"
    )
    order_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    booking_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'shop',
            'shop_name',
            'user',
            'user_name',
            'order',
            'order_id',
            'booking',
            'booking_id',
            'rating',
            'comment',
            'is_verified_buyer',
            'criterion_ratings',
            'criteria_ratings',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'is_verified_buyer', 'order', 'booking', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5 stars.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user if 'request' in self.context else None
        shop = attrs.get('shop')

        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication required to submit reviews.")

        if shop and shop.owner == user:
            raise serializers.ValidationError("Shop owners cannot review their own shop.")

        order_id = attrs.get('order_id')
        booking_id = attrs.get('booking_id')

        # 1. Booking-based review validation
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                raise serializers.ValidationError({"booking_id": "Specified booking does not exist."})

            if booking.customer != user:
                raise serializers.ValidationError({"booking_id": "You can only review bookings made by your account."})

            if booking.shop != shop:
                raise serializers.ValidationError({"booking_id": "Booking does not belong to this shop."})

            if booking.status != Booking.Status.COMPLETED:
                raise serializers.ValidationError({
                    "booking_id": f"Cannot review booking in '{booking.get_status_display()}' status. Only Completed bookings can be reviewed."
                })

            if Review.objects.filter(booking=booking).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError({"booking_id": "This booking has already been reviewed."})

            attrs['booking_obj'] = booking

        # 2. Order-based review validation
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                raise serializers.ValidationError({"order_id": "Specified order does not exist."})

            if order.customer != user:
                raise serializers.ValidationError({"order_id": "You can only review orders placed by your account."})

            if order.shop != shop:
                raise serializers.ValidationError({"order_id": "Order does not belong to this shop."})

            if order.status != Order.Status.COMPLETED:
                raise serializers.ValidationError({
                    "order_id": f"Cannot review order in '{order.get_status_display()}' status. Only Completed orders can be reviewed."
                })

            if Review.objects.filter(order=order).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError({"order_id": "This order has already been reviewed."})

            attrs['order_obj'] = order

        # 3. If neither order_id nor booking_id is provided, verify customer has at least one completed order/booking
        if not order_id and not booking_id and not self.instance:
            has_completed_order = Order.objects.filter(customer=user, shop=shop, status=Order.Status.COMPLETED).exists()
            has_completed_booking = Booking.objects.filter(customer=user, shop=shop, status=Booking.Status.COMPLETED).exists()

            if not (has_completed_order or has_completed_booking):
                raise serializers.ValidationError(
                    "You must have at least one Completed order or Completed booking with this shop to submit a verified review."
                )

        # 4. Duplicate review prevention per (shop, user)
        if not self.instance:
            if Review.objects.filter(shop=shop, user=user).exists():
                raise serializers.ValidationError("You have already reviewed this shop.")

        # 5. Validate criteria ratings payload
        criteria_list = attrs.get('criteria_ratings') or []
        shop_criteria = {c['slug']: c for c in shop.get_rating_criteria()}

        for crit in criteria_list:
            slug = crit.get('criterion_slug') or crit.get('slug')
            c_rating = crit.get('rating')

            if not slug or slug not in shop_criteria:
                raise serializers.ValidationError({
                    "criteria_ratings": f"Invalid criterion '{slug}' for this shop category."
                })
            try:
                c_rating_int = int(c_rating)
                if not (1 <= c_rating_int <= 5):
                    raise ValueError()
            except (ValueError, TypeError):
                raise serializers.ValidationError({
                    "criteria_ratings": f"Rating for criterion '{slug}' must be an integer between 1 and 5."
                })

        return attrs

    def create(self, validated_data):
        criteria_list = validated_data.pop('criteria_ratings', [])
        order_id = validated_data.pop('order_id', None)
        booking_id = validated_data.pop('booking_id', None)
        order_obj = validated_data.pop('order_obj', None)
        booking_obj = validated_data.pop('booking_obj', None)

        if order_obj:
            validated_data['order'] = order_obj
            validated_data['is_verified_buyer'] = True
        elif booking_obj:
            validated_data['booking'] = booking_obj
            validated_data['is_verified_buyer'] = True
        else:
            # Check completed history
            user = validated_data.get('user')
            shop = validated_data.get('shop')
            has_order = Order.objects.filter(customer=user, shop=shop, status=Order.Status.COMPLETED).first()
            has_booking = Booking.objects.filter(customer=user, shop=shop, status=Booking.Status.COMPLETED).first()
            if has_order:
                validated_data['order'] = has_order
                validated_data['is_verified_buyer'] = True
            elif has_booking:
                validated_data['booking'] = has_booking
                validated_data['is_verified_buyer'] = True

        with transaction.atomic():
            review = super().create(validated_data)
            shop = review.shop
            shop_criteria = {c['slug']: c for c in shop.get_rating_criteria()}

            for crit_data in criteria_list:
                slug = crit_data.get('criterion_slug') or crit_data.get('slug')
                score = int(crit_data.get('rating'))
                feedback = crit_data.get('feedback', '').strip()
                crit_def = shop_criteria.get(slug, {})

                criterion_instance = None
                if crit_def.get('id'):
                    criterion_instance = RatingCriterion.objects.filter(id=crit_def['id']).first()

                ReviewCriterionRating.objects.create(
                    review=review,
                    criterion=criterion_instance,
                    criterion_name=crit_def.get('name', slug),
                    criterion_name_ml=crit_def.get('name_ml', ''),
                    criterion_slug=slug,
                    rating=score,
                    feedback=feedback
                )

        return review


class ShopSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_interaction_mode = serializers.CharField(source='category.interaction_mode', read_only=True)
    products = ProductSerializer(many=True, read_only=True)
    working_hours = ShopWorkingHourSerializer(many=True, read_only=True)
    business_status = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(source='reviews.count', read_only=True)
    rating_summary = serializers.SerializerMethodField()
    rating_criteria = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            'id',
            'owner',
            'owner_name',
            'area',
            'category',
            'category_name',
            'category_interaction_mode',
            'business_type',
            'name',
            'description',
            'contact_phone',
            'whatsapp_number',
            'address',
            'ward_number',
            'latitude',
            'longitude',
            'opening_time',
            'closing_time',
            'is_open',
            'is_temporarily_closed',
            'temporary_close_reason',
            'business_status',
            'working_hours',
            'is_verified',
            'delivery_available',
            'delivery_radius_km',
            'delivery_fee',
            'todays_offer',
            'banner_image',
            'average_rating',
            'reviews_count',
            'rating_summary',
            'rating_criteria',
            'products',
            'created_at'
        ]
        read_only_fields = ['id', 'owner', 'is_verified', 'created_at']

    def get_business_status(self, obj):
        return obj.get_business_status()

    def get_average_rating(self, obj):
        avg = obj.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0.0

    def get_rating_summary(self, obj):
        return obj.get_rating_summary()

    def get_rating_criteria(self, obj):
        return obj.get_rating_criteria()


class PublicShopRegisterSerializer(serializers.Serializer):
    """
    All-in-one registration serializer for new shop owners.
    Creates User (role='shop_owner') and the Shop record in one atomic step.
    """
    owner_name = serializers.CharField(max_length=150, required=True)
    owner_phone = serializers.CharField(max_length=17, required=True)
    owner_password = serializers.CharField(min_length=6, write_only=True, required=True)

    shop_name = serializers.CharField(max_length=200, required=True)
    category_id = serializers.IntegerField(required=False, allow_null=True)
    contact_phone = serializers.CharField(max_length=17, required=False, allow_blank=True)
    whatsapp_number = serializers.CharField(max_length=17, required=False, allow_blank=True)
    ward_number = serializers.IntegerField(min_value=1, max_value=150, required=True)
    address = serializers.CharField(required=True)
    delivery_available = serializers.BooleanField(default=False)
    todays_offer = serializers.CharField(required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    area_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_owner_phone(self, value):
        cleaned_phone = value.strip().replace(" ", "")
        return cleaned_phone

    def create(self, validated_data):
        owner_name = validated_data.pop('owner_name')
        owner_phone = validated_data.pop('owner_phone')
        owner_password = validated_data.pop('owner_password')
        category_id = validated_data.pop('category_id', None)
        area_id = validated_data.pop('area_id', None)
        shop_name = validated_data.pop('shop_name')
        contact_phone = validated_data.pop('contact_phone', '') or owner_phone
        whatsapp_number = validated_data.pop('whatsapp_number', '')
        ward_number = validated_data.pop('ward_number')
        address = validated_data.pop('address')
        delivery_available = validated_data.pop('delivery_available', False)
        todays_offer = validated_data.pop('todays_offer', '')
        description = validated_data.pop('description', '')

        category = None
        if category_id:
            category = ShopCategory.objects.filter(id=category_id).first()

        area = None
        if area_id:
            area = Area.objects.filter(id=area_id).first()

        with transaction.atomic():
            user = User.objects.filter(phone_number=owner_phone).first()
            if user:
                if not user.check_password(owner_password):
                    raise serializers.ValidationError({
                        "owner_phone": "ഈ ഫോൺ നമ്പറിൽ ഇതിനകം അക്കൗണ്ട് ഉണ്ട്. നൽകിയ പാസ്‌വേഡ് ശരിയല്ല."
                    })
                if user.role != User.Role.SHOP_OWNER and user.role != User.Role.SUPER_ADMIN:
                    user.role = User.Role.SHOP_OWNER
                    user.save(update_fields=['role'])
            else:
                user = User.objects.create_user(
                    phone_number=owner_phone,
                    password=owner_password,
                    full_name=owner_name,
                    role=User.Role.SHOP_OWNER,
                    ward_number=ward_number,
                    area=area,
                    address=address
                )

            shop = Shop.objects.create(
                owner=user,
                name=shop_name,
                category=category,
                area=area,
                contact_phone=contact_phone,
                whatsapp_number=whatsapp_number,
                address=address,
                ward_number=ward_number,
                delivery_available=delivery_available,
                todays_offer=todays_offer,
                description=description,
                is_open=True,
                is_verified=False
            )

            token, _ = Token.objects.get_or_create(user=user)

            return {
                "message": "കട വിജയകരമായി രജിസ്റ്റർ ചെയ്തു! അഡ്മിൻ പരിശോധനയ്ക്ക് ശേഷം ലിസ്റ്റ് ചെയ്യപ്പെടും.",
                "token": token.key,
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "full_name": user.full_name,
                    "role": user.role,
                },
                "shop": {
                    "id": shop.id,
                    "name": shop.name,
                    "category": shop.category.name if shop.category else None,
                    "ward_number": shop.ward_number,
                    "contact_phone": shop.contact_phone,
                    "is_verified": shop.is_verified,
                }
            }

