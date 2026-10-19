from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.program_service import student_program, student_programs
from services.student_dashboard_service import dashboard


def _student(handler):
    user, err = require_role(handler, "STUDENT")
    if err: return None, (401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err)
    return user, None


def get_dashboard(handler):
    student, failure = _student(handler)
    if failure: return failure
    return 200, success_body(dashboard(student["id"]))


def list_my_programs(handler):
    student, failure = _student(handler)
    if failure: return failure
    return 200, success_body({"programs": student_programs(student["id"])})


def get_my_program(handler, program_id):
    student, failure = _student(handler)
    if failure: return failure
    try: return 200, success_body({"program": student_program(student["id"], program_id)})
    except ValueError as exc:
        return (403, error_body("FORBIDDEN", "This program is not assigned to your class.")) if str(exc) == "FORBIDDEN" else (404, error_body("NOT_FOUND", "Program not found."))
