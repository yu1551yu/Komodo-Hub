from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.learning_access_service import AccessError
from services.progress_service import student_program_progress, student_progress
from services.student_work_service import *
from models.submission_storage import read_attachment, save_attachment


def _student(handler):
    user, err = require_role(handler, "STUDENT")
    if err: return None, (401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err)
    return user, None


def _run(handler, action, status=200):
    student, failure = _student(handler)
    if failure: return failure
    try: return status, success_body(action(student))
    except AccessError as exc:
        return (404 if str(exc) == "NOT_FOUND" else 403), error_body(str(exc), "Resource not found." if str(exc) == "NOT_FOUND" else "You cannot access this resource.")
    except (ValueError, TypeError) as exc:
        return 400, error_body("VALIDATION_ERROR", "The supplied values are not valid.", {"reason": str(exc)})


def list_materials(handler, program_id): return _run(handler, lambda s: {"materials": student_materials(s["id"], program_id)})
def get_material(handler, material_id): return _run(handler, lambda s: {"material": student_material(s["id"], material_id)})
def list_activities(handler): return _run(handler, lambda s: {"activities": student_activities(s["id"])})
def get_activity(handler, activity_id): return _run(handler, lambda s: {"activity": student_activity(s["id"], activity_id)})
def get_submission(handler, activity_id): return _run(handler, lambda s: {"submission": submission_for(s["id"], activity_id)})
def post_submission(handler, activity_id, body): return _run(handler, lambda s: {"submission": save_submission(s["id"], activity_id, body)}, 201)
def patch_submission(handler, submission_id, body): return _run(handler, lambda s: {"submission": update_my_submission(s["id"], submission_id, body)})
def list_feedback(handler, submission_id): return _run(handler, lambda s: {"feedback": my_feedback(s["id"], submission_id)})
def reply_feedback(handler, submission_id, body): return _run(handler, lambda s: {"feedback": add_feedback(s, submission_id, body)}, 201)
def list_conversations(handler): return _run(handler, lambda s: {"conversations": conversations(s)})
def create_conversation(handler, body): return _run(handler, lambda s: {"conversation": get_or_create_conversation(s, str(body.get("participantId") or ""))}, 201)
def get_messages(handler, conversation_id): return _run(handler, lambda s: {"messages": conversation_messages(s, conversation_id)})
def post_message(handler, conversation_id, body): return _run(handler, lambda s: {"message": send_message(s, conversation_id, body)}, 201)
def read_messages(handler, conversation_id): return _run(handler, lambda s: {"markedRead": mark_read(s, conversation_id)})
def get_progress(handler): return _run(handler, lambda s: {"progress": student_progress(s["id"])})
def get_program_progress(handler, program_id): return _run(handler, lambda s: {"progress": student_program_progress(s["id"], program_id)})
def get_portfolio(handler): return _run(handler, lambda s: {"items": my_portfolio(s["id"])})
def post_portfolio(handler, body): return _run(handler, lambda s: {"item": add_portfolio_item(s["id"], body)}, 201)
def patch_portfolio(handler, item_id, body): return _run(handler, lambda s: {"item": update_portfolio_item(s["id"], item_id, body)})
def delete_portfolio(handler, item_id): return _run(handler, lambda s: {"removed": remove_portfolio_item(s["id"], item_id)})
def get_library_status(handler, submission_id): return _run(handler, lambda s: {"libraryItem": student_library_status(s["id"], submission_id)})
def upload_attachment(handler, body): return _run(handler, lambda s: {"attachment": save_attachment(s["id"], body)}, 201)


def attachment_bytes(handler, attachment_id):
    student, failure = _student(handler)
    if failure: return failure[0], None, None, failure[1]
    data, content_type = read_attachment(student["id"], attachment_id)
    if not data: return 404, None, None, error_body("NOT_FOUND", "Attachment not found.")
    return 200, data, content_type, None
