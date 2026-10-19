from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.learning_content_service import create_activity, create_material, edit_activity, edit_material, set_activity_status, set_material_status
from services.ownership_service import OwnershipError
from services.program_service import assign_classes, create_program, edit_program, set_program_status, teacher_program, teacher_programs
from models.activity_attachment_storage import save as save_activity_attachment


def _teacher(handler):
    teacher, err = require_role(handler, "TEACHER")
    if err: return None, (401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err)
    return teacher, None


def _failure(exc: Exception):
    code = str(exc)
    if code == "FORBIDDEN": return 403, error_body("FORBIDDEN", "You can only manage resources you own.")
    if code == "NOT_FOUND": return 404, error_body("NOT_FOUND", "Resource not found.")
    return 400, error_body("VALIDATION_ERROR", "The supplied values are not valid.", {"reason": code})


def list_programs(handler):
    teacher, failure = _teacher(handler)
    if failure: return failure
    return 200, success_body({"programs": teacher_programs(teacher["id"])})


def post_program(handler, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 201, success_body({"program": create_program(teacher["id"], body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def get_program(handler, program_id):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"program": teacher_program(teacher["id"], program_id)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def patch_program(handler, program_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"program": edit_program(teacher["id"], program_id, body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def program_classes(handler, program_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"program": assign_classes(teacher["id"], program_id, body.get("classIds") or [])})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def program_status(handler, program_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"program": set_program_status(teacher["id"], program_id, str(body.get("status") or ""))})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def post_material(handler, program_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 201, success_body({"material": create_material(teacher["id"], program_id, body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def patch_material(handler, material_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"material": edit_material(teacher["id"], material_id, body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def material_status(handler, material_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"material": set_material_status(teacher["id"], material_id, str(body.get("status") or ""))})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def post_activity(handler, program_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 201, success_body({"activity": create_activity(teacher["id"], program_id, body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def patch_activity(handler, activity_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"activity": edit_activity(teacher["id"], activity_id, body)})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def activity_status(handler, activity_id, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 200, success_body({"activity": set_activity_status(teacher["id"], activity_id, str(body.get("status") or ""))})
    except (ValueError, OwnershipError) as exc: return _failure(exc)


def upload_activity_attachment(handler, body):
    teacher, failure = _teacher(handler)
    if failure: return failure
    try: return 201, success_body({"attachment": save_activity_attachment(body)})
    except ValueError as exc: return _failure(exc)
