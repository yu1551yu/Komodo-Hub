from api.errors import error_body, success_body
from auth.middleware import require_auth
from services.notification_service import mark_read, notifications_for


def get(handler):
    actor, error = require_auth(handler)
    if error:
        return 401, error
    return 200, success_body({"notifications": notifications_for(actor["id"])})


def read(handler, body):
    actor, error = require_auth(handler)
    if error:
        return 401, error
    notification_id = str(body.get("notificationId") or "").strip() or None
    kind = str(body.get("kind") or "").strip() or None
    if not notification_id and not kind:
        return 400, error_body("VALIDATION_ERROR", "notificationId or kind is required.")
    return 200, success_body({"markedRead": mark_read(actor["id"], notification_id, kind)})
