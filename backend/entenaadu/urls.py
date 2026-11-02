from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    home_view,
    shop_list_view,
    shop_detail_view,
    web_submit_review,
    user_dashboard_view,
    shop_dashboard_view,
    admin_dashboard_view,
    web_shop_toggle_open,
    web_product_create,
    web_product_edit,
    web_product_toggle_stock,
    web_product_delete,
    web_order_create,
    web_order_update_status,
    web_order_cancel,
    web_complaint_create,
    web_complaint_delete,
    web_admin_verify_shop,
    web_admin_notice_create,
    web_notice_delete,
    web_admin_complaint_resolve,
    web_user_register_view,
    web_shop_register_view,
    web_login_view,
    web_logout_view,
    web_cart_view,
    web_cart_add,
    web_cart_update_qty,
    web_cart_remove,
    web_cart_clear,
    web_checkout_view,
    web_checkout_place_order,
    web_order_detail,
    web_booking_create,
    web_booking_update_status,
    web_booking_cancel,
    web_nearby_shops,
    web_shop_location_edit,
    web_shop_hours_edit,
    web_directory_submit,
    web_directory_delete,
    web_admin_verify_directory,
    web_admin_reject_directory,
    web_shop_progress_view,
    web_admin_shops_progress_view
)
from apps.chat.web_views import (
    web_find_friends,
    web_friends_list,
    web_chat_room,
    web_friend_request_send,
    web_friend_request_accept,
    web_friend_request_reject,
    web_friend_request_cancel,
    web_friend_unfriend,
    web_nearby_friends,
    web_location_settings
)

api_v1_patterns = [
    path('auth/', include('apps.accounts.urls')),
    path('shops/', include('apps.shops.urls')),
    path('orders/', include('apps.orders.urls')),
    path('events/', include('apps.events.urls')),
    path('complaints/', include('apps.complaints.urls')),
    path('directory/', include('apps.directory.urls')),
    path('ai/', include('apps.ai_assistant.urls')),
    path('chat/', include('apps.chat.urls')),
]

urlpatterns = [
    # Village Web Portal (Served directly via Django templates at ₹0 extra cost)
    path('', home_view, name='home'),

    # Public Shop Discovery & Detail
    path('shops/', shop_list_view, name='shop-list'),
    path('shops/nearby/', web_nearby_shops, name='nearby-shops'),
    path('shops/<int:shop_id>/', shop_detail_view, name='shop-detail'),
    path('shops/<int:shop_id>/review/', web_submit_review, name='shop-submit-review'),
    path('shops/<int:shop_id>/order/', web_order_create, name='order-create'),
    path('shops/<int:shop_id>/book/', web_booking_create, name='booking-create'),
    path('shops/<int:shop_id>/toggle-open/', web_shop_toggle_open, name='shop-toggle-open'),

    # Shopping Cart & Checkout Flow
    path('cart/', web_cart_view, name='cart-view'),
    path('cart/add/<int:product_id>/', web_cart_add, name='cart-add'),
    path('cart/item/<int:item_id>/update/', web_cart_update_qty, name='cart-update-qty'),
    path('cart/item/<int:item_id>/remove/', web_cart_remove, name='cart-remove-item'),
    path('cart/clear/', web_cart_clear, name='cart-clear'),
    path('checkout/', web_checkout_view, name='checkout-view'),
    path('checkout/place/', web_checkout_place_order, name='checkout-place-order'),
    path('orders/<int:order_id>/', web_order_detail, name='order-detail'),

    # User-to-User Friends & Private Chat
    path('friends/', web_friends_list, name='friends-list'),
    path('friends/find/', web_find_friends, name='find-friends'),
    path('friends/nearby/', web_nearby_friends, name='nearby-friends'),
    path('friends/location-settings/', web_location_settings, name='location-settings'),
    path('friends/request/send/<int:user_id>/', web_friend_request_send, name='friend-request-send'),
    path('friends/request/<int:request_id>/accept/', web_friend_request_accept, name='friend-request-accept'),
    path('friends/request/<int:request_id>/reject/', web_friend_request_reject, name='friend-request-reject'),
    path('friends/request/<int:request_id>/cancel/', web_friend_request_cancel, name='friend-request-cancel'),
    path('friends/unfriend/<int:user_id>/', web_friend_unfriend, name='friend-unfriend'),
    path('chat/', web_chat_room, name='chat-home'),
    path('chat/<int:friend_id>/', web_chat_room, name='chat-room'),

    # Role Dashboards
    path('dashboard/user/', user_dashboard_view, name='user-dashboard'),
    path('dashboard/shop/', shop_dashboard_view, name='shop-dashboard'),
    path('dashboard/shop/<int:shop_id>/progress/', web_shop_progress_view, name='shop-progress-detail'),
    path('dashboard/shop/<int:shop_id>/location/', web_shop_location_edit, name='shop-location-edit'),
    path('dashboard/shop/<int:shop_id>/hours/', web_shop_hours_edit, name='shop-hours-edit'),
    path('dashboard/admin/', admin_dashboard_view, name='admin-dashboard'),
    path('dashboard/admin/shops/progress/', web_admin_shops_progress_view, name='admin-shops-progress'),

    # Web Dashboard Actions
    path('dashboard/shop/<int:shop_id>/product/add/', web_product_create, name='product-create'),
    path('dashboard/shop/product/<int:product_id>/edit/', web_product_edit, name='product-edit'),
    path('dashboard/shop/product/<int:product_id>/toggle-stock/', web_product_toggle_stock, name='product-toggle-stock'),
    path('dashboard/shop/product/<int:product_id>/delete/', web_product_delete, name='product-delete'),
    path('dashboard/shop/order/<int:order_id>/status/', web_order_update_status, name='order-update-status'),
    path('dashboard/user/order/<int:order_id>/cancel/', web_order_cancel, name='order-cancel'),
    path('dashboard/shop/booking/<int:booking_id>/status/', web_booking_update_status, name='booking-update-status'),
    path('dashboard/user/booking/<int:booking_id>/cancel/', web_booking_cancel, name='booking-cancel'),
    path('dashboard/admin/shop/<int:shop_id>/verify/', web_admin_verify_shop, name='admin-verify-shop'),
    path('dashboard/admin/directory/<int:entry_id>/verify/', web_admin_verify_directory, name='admin-verify-directory'),
    path('dashboard/admin/directory/<int:entry_id>/reject/', web_admin_reject_directory, name='admin-reject-directory'),
    path('dashboard/admin/notice/create/', web_admin_notice_create, name='admin-notice-create'),
    path('dashboard/admin/notice/<int:notice_id>/delete/', web_notice_delete, name='notice-delete'),
    path('dashboard/admin/complaint/<int:complaint_id>/resolve/', web_admin_complaint_resolve, name='admin-complaint-resolve'),
    path('directory/submit/', web_directory_submit, name='directory-submit'),
    path('directory/<int:entry_id>/delete/', web_directory_delete, name='directory-delete'),
    path('complaints/create/', web_complaint_create, name='complaint-create'),
    path('dashboard/complaint/<int:complaint_id>/delete/', web_complaint_delete, name='complaint-delete'),

    # Auth & Registrations
    path('register/user/', web_user_register_view, name='web-user-register'),
    path('register/shop/', web_shop_register_view, name='web-shop-register'),
    path('auth/login/', web_login_view, name='web-login'),
    path('auth/logout/', web_logout_view, name='web-logout'),

    # Django Administration Panel (Secured, staff only)
    path('admin/', admin.site.urls),

    # REST API v1
    path('api/v1/', include(api_v1_patterns)),

    # Legacy/convenience alias
    path('api/', include(api_v1_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
