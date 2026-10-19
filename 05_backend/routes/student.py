from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_role
from services.enrollment_service import student_classes
from services.student_profile_service import (
    get_student_avatar_bytes,
    get_student_profile,
    patch_student_profile,
    upload_student_avatar,
)


def handle_my_classes(handler) -> tuple[int, dict]:
    user, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return student_classes(user["id"])


def handle_my_profile(handler) -> tuple[int, dict]:
    user, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return get_student_profile(user["id"])


def handle_patch_my_profile(handler, body: dict | None) -> tuple[int, dict]:
    user, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return patch_student_profile(user["id"], body)


def handle_upload_avatar(handler, body: dict | None) -> tuple[int, dict]:
    user, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return upload_student_avatar(user["id"], body)


def handle_get_avatar(handler) -> tuple[int, bytes | None, str | None, dict | None]:
    user, err = require_role(handler, "STUDENT")
    if err:
        code = 401 if err["error"]["code"] == "UNAUTHORIZED" else 403
        return code, None, None, err
    return get_student_avatar_bytes(user["id"])


def handle_dashboard(handler) -> tuple[int, dict]:
    user, err = require_role(handler, "STUDENT")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return 200, success_body(
        {
            "dashboard": "STUDENT",
            "message": "Welcome to the Student Dashboard.",
            "user": user,
        }
    )
