from django.contrib import admin
from .models import (
    ShopCategory,
    Shop,
    Product,
    Review,
    ShopWorkingHour,
    RatingCriterion,
    ReviewCriterionRating
)

@admin.register(ShopCategory)
class ShopCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_type', 'interaction_mode', 'icon_name')
    list_filter = ('business_type', 'interaction_mode')
    search_fields = ('name',)

@admin.register(RatingCriterion)
class RatingCriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_ml', 'category', 'business_type', 'is_active', 'order', 'slug')
    list_filter = ('is_active', 'business_type', 'category')
    search_fields = ('name', 'name_ml', 'slug', 'description')
    list_editable = ('is_active', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')

class ProductInline(admin.TabularInline):
    model = Product
    extra = 1

class ShopWorkingHourInline(admin.TabularInline):
    model = ShopWorkingHour
    extra = 7
    max_num = 7

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'owner', 'contact_phone', 'ward_number', 'is_open', 'is_temporarily_closed', 'is_verified', 'delivery_available')
    list_filter = ('category', 'category__interaction_mode', 'ward_number', 'is_open', 'is_temporarily_closed', 'is_verified', 'delivery_available')
    search_fields = ('name', 'contact_phone', 'owner__full_name')
    inlines = [ShopWorkingHourInline, ProductInline]

@admin.register(ShopWorkingHour)
class ShopWorkingHourAdmin(admin.ModelAdmin):
    list_display = ('shop', 'day', 'opening_time', 'closing_time', 'is_closed')
    list_filter = ('day', 'is_closed')
    search_fields = ('shop__name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'discount_price', 'unit', 'service_duration_minutes', 'is_available')
    list_filter = ('is_available', 'shop__category')
    search_fields = ('name', 'shop__name')

class ReviewCriterionRatingInline(admin.TabularInline):
    model = ReviewCriterionRating
    extra = 0
    readonly_fields = ('criterion_name', 'criterion_name_ml', 'criterion_slug', 'created_at')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('shop', 'user', 'rating', 'order', 'booking', 'is_verified_buyer', 'created_at')
    list_filter = ('rating', 'is_verified_buyer', 'created_at', 'shop__category')
    search_fields = ('shop__name', 'user__full_name', 'comment')
    inlines = [ReviewCriterionRatingInline]

@admin.register(ReviewCriterionRating)
class ReviewCriterionRatingAdmin(admin.ModelAdmin):
    list_display = ('review', 'criterion_name', 'rating', 'feedback', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('criterion_name', 'criterion_slug', 'feedback', 'review__shop__name')
