import logging
from apps.accounts.models import AuditLog

logger = logging.getLogger(__name__)

def log_audit(performed_by, action, target_type, target_id, target_identifier='', reason=''):
    """
    Centralized, fail-safe audit logging utility for Ente Naadu.
    Records administrative, financial, and access-control actions in AuditLog.

    Parameters:
    - performed_by: User instance who triggered the action
    - action: AuditLog.Action choice value (e.g., 'product_create', 'order_status_update')
    - target_type: Model name or category ('Shop', 'Product', 'Order', 'Booking', 'DirectoryEntry')
    - target_id: ID of the modified entity
    - target_identifier: Human-readable name or order/booking number
    - reason: Contextual explanation or status change description
    """
    try:
        if not performed_by or not getattr(performed_by, 'is_authenticated', False):
            user_ref = None
        else:
            user_ref = performed_by

        audit_entry = AuditLog.objects.create(
            performed_by=user_ref,
            action=action,
            target_type=str(target_type)[:100],
            target_id=int(target_id) if target_id is not None else 0,
            target_identifier=str(target_identifier)[:200],
            reason=str(reason) if reason else f"Action {action} performed on {target_type} #{target_id}"
        )
        return audit_entry
    except Exception as e:
        logger.error(f"Audit log failed for action {action} on {target_type} #{target_id}: {e}", exc_info=True)
        return None
