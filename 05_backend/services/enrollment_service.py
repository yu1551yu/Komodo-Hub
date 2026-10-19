from __future__ import annotations

from api.errors import error_body, success_body
from models.class_repository import find_by_access_code, find_by_id, is_access_code_valid, public_class
from models.enrollment_repository import create_enrollment, find_enrollment, list_for_student
from models.user_repository import find_by_id as find_user_by_id


def resolve_class_by_access_code(access_code: str) -> tuple[dict | None, tuple[int, dict] | None]:
    """Return (class, None) or (None, (http_status, error_body))."""
    code = str(access_code or "").strip()
    if not code:
        return None, (
            400,
            error_body(
                "VALIDATION_ERROR",
                "Access code is required.",
                {"field": "accessCode"},
            ),
        )
    cls = find_by_access_code(code)
    if not cls:
        return None, (
            404,
            error_body(
                "INVALID_ACCESS_CODE",
                "Invalid or unknown access code. Use the code shown in your teacher's Classroom (server), not a demo-only code.",
            ),
        )
    if not is_access_code_valid(cls):
        return None, (400, error_body("ACCESS_CODE_EXPIRED", "This access code has expired."))
    return cls, None


def join_class_by_access_code(student_id: str, access_code: str) -> tuple[int, dict]:
    cls, err = resolve_class_by_access_code(access_code)
    if err:
        return err

    student = find_user_by_id(student_id)
    if not student or student.get("role") != "STUDENT":
        return 403, error_body("FORBIDDEN", "Only students can join classes.")

    assert cls is not None
    if find_enrollment(student_id, cls["id"]):
        return 409, error_body("ALREADY_ENROLLED", "You are already enrolled in this class.")

    try:
        enrollment = create_enrollment(student_id, cls["id"])
    except ValueError as e:
        if str(e) == "ALREADY_ENROLLED":
            return 409, error_body("ALREADY_ENROLLED", "You are already enrolled in this class.")
        raise

    return 200, success_body(
        {
            "enrollment": enrollment,
            "class": public_class(cls),
        }
    )


def student_classes(student_id: str) -> tuple[int, dict]:
    student = find_user_by_id(student_id)
    if not student or student.get("role") != "STUDENT":
        return 403, error_body("FORBIDDEN", "Only students have class enrollments.")

    enrollments = list_for_student(student_id)
    classes = []
    for enr in enrollments:
        cls = find_by_id(enr["classId"])
        if not cls:
            continue
        classes.append(
            {
                **public_class(cls),
                "joinedAt": enr.get("joinedAt"),
                "enrollmentId": enr.get("id"),
            }
        )
    return 200, success_body({"classes": classes})
