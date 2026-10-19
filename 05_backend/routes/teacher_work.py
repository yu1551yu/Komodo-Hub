from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.learning_access_service import AccessError
from services.ownership_service import OwnershipError
from services.progress_service import teacher_class_progress, teacher_student_progress, teacher_student_report
from services.student_work_service import *
from services.review_reminder_service import utc_now, with_review_state


def _teacher(handler):
    user, err = require_role(handler, "TEACHER")
    if err: return None, (401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err)
    return user, None


def _run(handler, action, status=200):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return status, success_body(action(teacher))
    except (AccessError, OwnershipError) as exc: return (404 if str(exc) == "NOT_FOUND" else 403), error_body(str(exc), "Resource not found." if str(exc) == "NOT_FOUND" else "You cannot access this resource.")
    except (ValueError, TypeError) as exc: return 400, error_body("VALIDATION_ERROR", "The supplied values are not valid.", {"reason": str(exc)})


def list_submissions(handler, activity_id, status=None):
    now = utc_now()
    return _run(handler, lambda t: {"submissions": [with_review_state(row, now) for row in teacher_submissions(t["id"], activity_id, status)]})


def get_submission(handler, submission_id): return _run(handler, lambda t: {"submission": with_review_state(teacher_submission(t["id"], submission_id))})
def return_student_submission(handler, submission_id, body): return _run(handler, lambda t: {"submission": return_submission(t["id"], submission_id, body)})
def post_feedback(handler, submission_id, body): return _run(handler, lambda t: {"feedback": add_feedback(t, submission_id, body)}, 201)
def patch_feedback(handler, feedback_id, body): return _run(handler, lambda t: {"feedback": edit_feedback(t["id"], feedback_id, body)})
def list_conversations(handler): return _run(handler, lambda t: {"conversations": conversations(t)})
def create_conversation(handler, body): return _run(handler, lambda t: {"conversation": get_or_create_conversation(t, str(body.get("participantId") or ""))}, 201)
def get_messages(handler, conversation_id): return _run(handler, lambda t: {"messages": conversation_messages(t, conversation_id)})
def post_message(handler, conversation_id, body): return _run(handler, lambda t: {"message": send_message(t, conversation_id, body)}, 201)
def read_messages(handler, conversation_id): return _run(handler, lambda t: {"markedRead": mark_read(t, conversation_id)})
def get_class_progress(handler, class_id): return _run(handler, lambda t: {"progress": teacher_class_progress(t["id"], class_id)})
def get_student_progress(handler, student_id): return _run(handler, lambda t: {"progress": teacher_student_progress(t["id"], student_id)})
def get_report(handler, student_id, program_id): return _run(handler, lambda t: {"report": teacher_student_report(t["id"], student_id, program_id)})
def put_library(handler, submission_id, body): return _run(handler, lambda t: {"libraryItem": upsert_library_item(t["id"], submission_id, body)})
