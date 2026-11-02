import logging
from apps.chat.models import SocialNotification

logger = logging.getLogger(__name__)

def send_notification(recipient, actor, ntype, title, body, link_url=''):
    """
    Unified in-app notification dispatcher for Ente Naadu platform.
    Works at ₹0 infrastructure cost using existing database-backed notification system.
    """
    if not recipient or not getattr(recipient, 'id', None):
        return None

    # Don't notify oneself
    if actor and getattr(actor, 'id', None) == recipient.id:
        return None

    try:
        notif = SocialNotification.objects.create(
            recipient=recipient,
            actor=actor if actor and getattr(actor, 'is_authenticated', False) else None,
            notification_type=ntype,
            title=str(title)[:200],
            body=str(body)[:400],
            link_url=str(link_url)[:255]
        )
        return notif
    except Exception as e:
        logger.error(f"Failed to dispatch notification to user {getattr(recipient, 'id', None)}: {e}", exc_info=True)
        return None


def notify_order_created(order):
    """Notifies the shop owner when a new order is placed."""
    if not order or not hasattr(order, 'shop') or not order.shop.owner:
        return None

    return send_notification(
        recipient=order.shop.owner,
        actor=order.customer,
        ntype=SocialNotification.Type.ORDER_UPDATE,
        title=f"പുതിയ ഓർഡർ #{order.id} 🛍️",
        body=f"ഉപഭോക്താവ് {order.customer.full_name} ₹{order.total_amount} രൂപയുടെ ഓർഡർ നൽകി.",
        link_url=f"/orders/{order.id}/"
    )


def notify_order_status_changed(order):
    """Notifies the customer when their order status is updated by the shop."""
    if not order or not order.customer:
        return None

    status_name = order.get_status_display() if hasattr(order, 'get_status_display') else order.status
    return send_notification(
        recipient=order.customer,
        actor=order.shop.owner if hasattr(order, 'shop') and order.shop else None,
        ntype=SocialNotification.Type.ORDER_UPDATE,
        title=f"ഓർഡർ #{order.id} - {status_name}",
        body=f"{order.shop.name}: നിങ്ങളുടെ ഓർഡർ സ്റ്റാറ്റസ് '{status_name}' ആയി പുതുക്കി.",
        link_url=f"/orders/{order.id}/"
    )


def notify_booking_requested(booking):
    """Notifies the shop/salon/service owner of a new appointment booking request."""
    if not booking or not hasattr(booking, 'shop') or not booking.shop.owner:
        return None

    service_name = booking.service.name if booking.service else "അപ്പോയിന്റ്മെന്റ്"
    return send_notification(
        recipient=booking.shop.owner,
        actor=booking.customer,
        ntype=SocialNotification.Type.BOOKING_UPDATE,
        title=f"പുതിയ ബുക്കിംഗ് #{booking.id} 📅",
        body=f"{booking.customer.full_name} ({service_name}) {booking.booking_date} തീയതിയിൽ ({booking.time_slot}) ബുക്ക് ചെയ്തു.",
        link_url="/dashboard/shop/"
    )


def notify_booking_status_changed(booking, performed_by=None):
    """Notifies customer (or shop owner if cancelled by customer) of booking status change."""
    if not booking:
        return None

    status_name = booking.get_status_display() if hasattr(booking, 'get_status_display') else booking.status

    # If customer cancelled, notify the shop owner
    if performed_by and performed_by.id == booking.customer_id:
        recipient = booking.shop.owner if hasattr(booking, 'shop') and booking.shop else None
        target_link = "/dashboard/shop/"
        msg = f"{booking.customer.full_name} #{booking.id} അപ്പോയിന്റ്മെന്റ് റദ്ദാക്കി."
    else:
        # Shop owner confirmed/cancelled/completed, notify the customer
        recipient = booking.customer
        target_link = "/dashboard/user/"
        msg = f"{booking.shop.name}-ലെ നിങ്ങളുടെ അപ്പോയിന്റ്മെന്റ് #{booking.id} സ്റ്റാറ്റസ് '{status_name}' ആയി പുതുക്കി."

    if not recipient:
        return None

    return send_notification(
        recipient=recipient,
        actor=performed_by,
        ntype=SocialNotification.Type.BOOKING_UPDATE,
        title=f"ബുക്കിംഗ് #{booking.id} - {status_name}",
        body=msg,
        link_url=target_link
    )


def notify_directory_status(entry, is_approved, admin_user=None):
    """Notifies submitter when their directory entry is approved or rejected."""
    if not entry or not entry.submitted_by:
        return None

    title = "സേവന ഡയറക്ടറി അംഗീകരിച്ചു ✓" if is_approved else "സേവന ഡയറക്ടറി നിരസിച്ചു"
    body = f"നിങ്ങൾ സമർപ്പിച്ച '{entry.name}' ({entry.get_category_display()}) അഡ്മിൻ പരിശോധിച്ചു അംഗീകരിച്ചു." if is_approved else f"നിങ്ങൾ സമർപ്പിച്ച '{entry.name}' വിവരങ്ങൾ അപൂർണ്ണമായതിനാൽ നിരസിച്ചു."

    return send_notification(
        recipient=entry.submitted_by,
        actor=admin_user,
        ntype=SocialNotification.Type.DIRECTORY_UPDATE,
        title=title,
        body=body,
        link_url="/dashboard/user/"
    )


def notify_complaint_status(complaint, admin_user=None):
    """Notifies citizen when their reported civic complaint is resolved."""
    if not complaint or complaint.is_anonymous or not complaint.citizen:
        return None

    return send_notification(
        recipient=complaint.citizen,
        actor=admin_user,
        ntype=SocialNotification.Type.COMPLAINT_UPDATE,
        title=f"പരാതി #{complaint.id} പരിഹരിച്ചു ✓",
        body=f"നിങ്ങൾ നൽകിയ '{complaint.title}' വാർഡ് പ്രതിനിധി പരിഹരിച്ചു.",
        link_url="/dashboard/user/"
    )
