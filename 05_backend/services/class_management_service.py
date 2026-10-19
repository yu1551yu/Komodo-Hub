from __future__ import annotations

from models.class_repository import public_class, update_class
from models.enrollment_repository import list_student_ids_for_class, remove_enrollment
from models.user_repository import find_by_id, public_user
from services.ownership_service import owned_class


def class_detail(teacher_id: str, class_id: str) -> dict:
    row = owned_class(teacher_id, class_id)
    students = []
    for student_id in list_student_ids_for_class(class_id):
        user = find_by_id(student_id)
        if user and user.get("role") == "STUDENT":
            students.append(public_user(user))
    return {**public_class(row), "studentCount": len(students), "students": students}


def edit_class(teacher_id: str, class_id: str, body: dict) -> dict:
    owned_class(teacher_id, class_id)
    patch = {key: body.get(key) for key in ("name", "description", "grade") if key in body}
    if "name" in patch and len(str(patch["name"] or "").strip()) < 2:
        raise ValueError("INVALID_NAME")
    if not patch:
        raise ValueError("EMPTY_PATCH")
    return public_class(update_class(class_id, patch) or {})


def remove_student(teacher_id: str, class_id: str, student_id: str) -> bool:
    owned_class(teacher_id, class_id)
    return remove_enrollment(student_id, class_id)
