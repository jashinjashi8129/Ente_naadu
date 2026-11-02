from rest_framework import permissions

def is_admin_user(user):
    """Returns True if the user is authenticated and is staff or super_admin."""
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or getattr(user, 'role', None) == 'super_admin'

def is_ward_admin_or_higher(user):
    """Returns True if the user is staff, super_admin, or ward_admin."""
    if not user or not user.is_authenticated:
        return False
    return user.is_staff or getattr(user, 'role', None) in ['super_admin', 'ward_admin']


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission:
    - SAFE_METHODS (GET, HEAD, OPTIONS) allowed for all.
    - Write/Delete allowed only if request.user owns the object (obj.owner or obj.user) or is admin.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if is_admin_user(request.user):
            return True

        # Check for standard ownership attributes
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'customer'):
            return obj.customer == request.user
        return False


class IsShopOwner(permissions.BasePermission):
    """
    Object-level permission for Shops and Shop-owned entities (Products, Services):
    - SAFE_METHODS allowed for anyone (or viewset permission).
    - Modification allowed ONLY for the verified shop owner or super admin.
    - Explicitly blocks Shop Owner B from altering Shop Owner A's shop, products, or stock.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        if is_admin_user(request.user):
            return True

        # Direct shop object
        if hasattr(obj, 'owner'):
            return obj.owner == request.user

        # Child object linked via shop (Product, Service)
        if hasattr(obj, 'shop') and hasattr(obj.shop, 'owner'):
            return obj.shop.owner == request.user

        return False


class IsOrderParticipant(permissions.BasePermission):
    """
    Object-level permission for Orders:
    - Allowed ONLY for the customer who placed the order,
      the shop owner fulfilling the order, or super admin.
    - Blocks Customer B from accessing Customer A's private orders.
    - Blocks Shop Owner B from accessing Shop Owner A's orders.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin_user(user):
            return True

        is_customer = (getattr(obj, 'customer', None) == user)
        is_owner = (hasattr(obj, 'shop') and getattr(obj.shop, 'owner', None) == user)
        return is_customer or is_owner


class IsBookingParticipant(permissions.BasePermission):
    """
    Object-level permission for Appointments and Bookings:
    - Allowed ONLY for the customer who booked the slot,
      the shop/service owner providing the service, or super admin.
    - Blocks Customer B from reading/cancelling Customer A's appointments.
    - Blocks Business B from modifying Business A's appointments.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin_user(user):
            return True

        is_customer = (getattr(obj, 'customer', None) == user)
        is_owner = (hasattr(obj, 'shop') and getattr(obj.shop, 'owner', None) == user)
        return is_customer or is_owner


class IsServiceRequestParticipant(permissions.BasePermission):
    """
    Object-level permission for Custom Service / Prescription Requests:
    - Allowed ONLY for the customer or the shop owner receiving the request.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin_user(user):
            return True

        is_customer = (getattr(obj, 'customer', None) == user)
        is_owner = (hasattr(obj, 'shop') and getattr(obj.shop, 'owner', None) == user)
        return is_customer or is_owner


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission: Allows read-only access for all, but restricts writes
    to Ward Admins, Super Admins, and Staff.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_ward_admin_or_higher(request.user)


class IsSuperAdminUser(permissions.BasePermission):
    """
    Restricts access strictly to Super Admins and Staff.
    """
    def has_permission(self, request, view):
        return is_admin_user(request.user)
