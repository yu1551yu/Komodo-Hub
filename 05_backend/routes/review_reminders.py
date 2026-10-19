from api.errors import error_body, success_body
from auth.middleware import require_role
from services.review_reminder_service import teacher_review_summary


def summary(handler):
    teacher, error = require_role(handler, "TEACHER")
    if error:
        return (401 if error["error"]["code"] == "UNAUTHORIZED" else 403), error
    try:
        return 200, success_body({"reviewSummary": teacher_review_summary(teacher["id"])})
    except Exception:
        return 503, error_body("REVIEW_REMINDERS_UNAVAILABLE", "Review reminders are temporarily unavailable. Please refresh to retry.")
