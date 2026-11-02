from django.contrib import admin
from .models import Order, OrderItem, Booking, ServiceRequest

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'quantity', 'unit_price', 'subtotal')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'customer', 'customer_phone', 'status', 'delivery_type', 'total_amount', 'created_at')
    list_filter = ('status', 'delivery_type', 'created_at')
    search_fields = ('id', 'customer__full_name', 'customer_phone', 'shop__name')
    inlines = [OrderItemInline]
    ordering = ('-created_at',)

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'customer', 'customer_phone', 'booking_date', 'time_slot', 'status', 'created_at')
    list_filter = ('status', 'booking_date', 'created_at')
    search_fields = ('customer__full_name', 'customer_phone', 'shop__name')

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'customer', 'request_type', 'status', 'quoted_price', 'created_at')
    list_filter = ('request_type', 'status', 'created_at')
    search_fields = ('customer__full_name', 'shop__name', 'description')
