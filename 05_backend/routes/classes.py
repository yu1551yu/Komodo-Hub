from __future__ import annotations

from api.errors import error_body
from api.validation import validate_join_class
from auth.middleware import require_role
from services.enrollment_service import join_class_by_access_code


def handle_join_class(handler, body: dict | None) -> tuple[int, dict]:
    student, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err

    if body and body.get("classId"):
        return 400, error_body(
            "VALIDATION_ERROR",
            "Join by access code only. Do not send classId.",
            {"field": "classId"},
        )

    err_code, parsed = validate_join_class(body or {})
    if err_code:
        if err_code == "INVALID_BODY":
            return 400, error_body("INVALID_BODY", "Request body must be JSON.")
        return 400, error_body(err_code, parsed["message"], parsed)

    return join_class_by_access_code(student["id"], parsed["accessCode"])
