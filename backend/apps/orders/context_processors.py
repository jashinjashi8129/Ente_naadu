from .models import Cart


def cart_context(request):
    """
    Provides global cart statistics (item count, total amount, and cart object)
    to all Django templates for seamless navbar badge and action rendering.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'cart_item_count': 0,
            'cart_total': 0,
            'cart_obj': None,
        }

    try:
        cart = Cart.objects.prefetch_related('items__product').filter(customer=request.user).first()
        if cart:
            return {
                'cart_item_count': cart.total_items,
                'cart_total': cart.total_amount,
                'cart_obj': cart,
            }
    except Exception:
        pass

    return {
        'cart_item_count': 0,
        'cart_total': 0,
        'cart_obj': None,
    }
