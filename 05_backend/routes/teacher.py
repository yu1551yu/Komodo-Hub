from __future__ import annotations

from api.errors import error_body, success_body
from api.validation import validate_create_class
from auth.middleware import require_role
from models.class_repository import (
    create_class,
    list_by_teacher,
    public_class,
    regenerate_access_code,
)
from models.enrollment_repository import list_student_ids_for_class
from models.user_repository import find_by_id, public_user, update_user
from services.class_management_service import class_detail, edit_class, remove_student
from services.ownership_service import OwnershipError


def _ownership_error(exc: OwnershipError) -> tuple[int, dict]:
    if str(exc) == "NOT_FOUND":
        return 404, error_body("NOT_FOUND", "Class not found.")
    return 403, error_body("FORBIDDEN", "You can only manage your own classes.")


def handle_list_classes(handler) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    return 200, success_body({"classes": list_by_teacher(teacher["id"])})


def handle_create_class(handler, body: dict | None) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    err_code, parsed = validate_create_class(body or {})
    if err_code:
        if err_code == "INVALID_BODY":
            return 400, error_body("INVALID_BODY", "Request body must be JSON.")
        return 400, error_body(err_code, parsed["message"], parsed)
    try:
        cls = create_class(teacher["id"], parsed["name"], (body or {}).get("description", ""), (body or {}).get("grade", ""))
    except ValueError as e:
        if str(e) == "INVALID_NAME":
            return 400, error_body("VALIDATION_ERROR", "Class name is required.", {"field": "name"})
        raise
    record = find_by_id(teacher["id"])
    if record:
        class_ids = list(record.get("teacherClassIds") or [])
        if cls["id"] not in class_ids:
            update_user(teacher["id"], {"teacherClassIds": class_ids + [cls["id"]]})
    return 201, success_body({"class": public_class(cls)})


def handle_regenerate_access_code(handler, class_id: str) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    try:
        cls = regenerate_access_code(teacher["id"], class_id)
    except ValueError as e:
        if str(e) == "FORBIDDEN":
            return 403, error_body("FORBIDDEN", "You can only manage your own classes.")
        raise
    if not cls:
        return 404, error_body("NOT_FOUND", "Class not found.")
    return 200, success_body({"class": public_class(cls)})


def handle_get_class(handler, class_id: str) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err: return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    try: return 200, success_body({"class": class_detail(teacher["id"], class_id)})
    except OwnershipError as exc: return _ownership_error(exc)


def handle_patch_class(handler, class_id: str, body: dict) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err: return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    try: return 200, success_body({"class": edit_class(teacher["id"], class_id, body)})
    except OwnershipError as exc: return _ownership_error(exc)
    except ValueError as exc: return 400, error_body("VALIDATION_ERROR", "Provide a valid class name or editable field.", {"reason": str(exc)})


def handle_class_students(handler, class_id: str) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err: return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    try:
        detail = class_detail(teacher["id"], class_id)
        return 200, success_body({"students": detail["students"]})
    except OwnershipError as exc: return _ownership_error(exc)


def handle_remove_student(handler, class_id: str, student_id: str) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err: return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    try:
        if not remove_student(teacher["id"], class_id, student_id):
            return 404, error_body("NOT_FOUND", "Student is not enrolled in this class.")
        return 200, success_body({"removed": True})
    except OwnershipError as exc: return _ownership_error(exc)


def _class_with_roster(cls: dict) -> tuple[dict, list[dict]]:
    roster: list[dict] = []
    student_ids = list_student_ids_for_class(cls["id"])
    for sid in student_ids:
        u = find_by_id(sid)
        if u and u.get("role") == "STUDENT":
            roster.append(public_user(u))
    enriched = {
        **cls,
        "studentIds": student_ids,
        "studentCount": len(roster),
    }
    return enriched, roster


def handle_list_students(handler) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    raw_classes = list_by_teacher(teacher["id"])
    students_map: dict[str, dict] = {}
    class_roster: list[dict] = []
    classes: list[dict] = []
    for cls in raw_classes:
        enriched, roster = _class_with_roster(cls)
        classes.append(enriched)
        for student in roster:
            students_map[student["id"]] = student
        class_roster.append(
            {
                "class": enriched,
                "students": roster,
                "studentCount": len(roster),
            }
        )
    return 200, success_body(
        {
            "students": list(students_map.values()),
            "classes": classes,
            "classRoster": class_roster,
        }
    )


def handle_get_student(handler, student_id: str) -> tuple[int, dict]:
    teacher, err = require_role(handler, "TEACHER")
    if err:
        return 401 if err["error"]["code"] == "UNAUTHORIZED" else 403, err
    student = find_by_id(student_id)
    if not student or student.get("role") != "STUDENT":
        return 404, error_body("NOT_FOUND", "Student not found.")
    teacher_classes = {c["id"] for c in list_by_teacher(teacher["id"])}
    enrolled = any(
        student_id in list_student_ids_for_class(cid) for cid in teacher_classes
    )
    if not enrolled:
        return 403, error_body("FORBIDDEN", "You can only access students in your classes.")
    return 200, success_body({"student": public_user(student)})
