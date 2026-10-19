from __future__ import annotations

from models.class_repository import find_by_id as find_class
from models.enrollment_repository import list_for_student
from models.learning_activity_repository import find_by_id as find_activity
from models.program_class_repository import class_ids_for_program
from models.program_repository import find_by_id as find_program
from services.ownership_service import OwnershipError, owned_program


class AccessError(ValueError):
    pass


def student_class_ids(student_id: str) -> set[str]:
    return {row["classId"] for row in list_for_student(student_id)}


def require_student_program(student_id: str, program_id: str) -> dict:
    program = find_program(program_id)
    if not program or program.get("status") != "published":
        raise AccessError("NOT_FOUND")
    if not student_class_ids(student_id).intersection(class_ids_for_program(program_id)):
        raise AccessError("FORBIDDEN")
    return program


def require_student_activity(student_id: str, activity_id: str) -> dict:
    activity = find_activity(activity_id)
    if not activity or activity.get("status") not in {"published", "closed"}:
        raise AccessError("NOT_FOUND")
    require_student_program(student_id, activity["programId"])
    return activity


def teacher_student_class_ids(teacher_id: str, student_id: str) -> set[str]:
    result = set()
    for enrollment in list_for_student(student_id):
        class_row = find_class(enrollment["classId"])
        if class_row and class_row.get("teacherId") == teacher_id:
            result.add(class_row["id"])
    return result


def require_teacher_student(teacher_id: str, student_id: str) -> set[str]:
    class_ids = teacher_student_class_ids(teacher_id, student_id)
    if not class_ids:
        raise AccessError("FORBIDDEN")
    return class_ids


def require_teacher_activity(teacher_id: str, activity_id: str) -> dict:
    activity = find_activity(activity_id)
    if not activity:
        raise AccessError("NOT_FOUND")
    try:
        owned_program(teacher_id, activity["programId"])
    except OwnershipError as exc:
        raise AccessError(str(exc)) from exc
    return activity


def require_teacher_submission_relationship(teacher_id: str, submission: dict) -> dict:
    activity = require_teacher_activity(teacher_id, submission["activityId"])
    shared_classes = require_teacher_student(teacher_id, submission["studentId"])
    if not shared_classes.intersection(class_ids_for_program(activity["programId"])):
        raise AccessError("FORBIDDEN")
    return activity
