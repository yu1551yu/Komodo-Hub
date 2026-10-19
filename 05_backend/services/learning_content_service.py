from __future__ import annotations

from models.learning_activity_repository import create as create_activity_row, find_by_id as find_activity, update as update_activity_row
from models.material_repository import create as create_material_row, find_by_id as find_material, update as update_material_row
from services.ownership_service import owned_program


def _validate_title(body: dict) -> None:
    if len(str(body.get("title") or "").strip()) < 2:
        raise ValueError("INVALID_TITLE")


def create_material(teacher_id: str, program_id: str, body: dict) -> dict:
    owned_program(teacher_id, program_id); _validate_title(body)
    return create_material_row(program_id, teacher_id, {**body, "status": "published"})


def edit_material(teacher_id: str, material_id: str, body: dict) -> dict:
    row = find_material(material_id)
    if not row: raise ValueError("NOT_FOUND")
    owned_program(teacher_id, row["programId"])
    if "title" in body: _validate_title(body)
    return update_material_row(material_id, body) or row


def set_material_status(teacher_id: str, material_id: str, status: str) -> dict:
    if status not in {"draft", "published"}: raise ValueError("INVALID_STATUS")
    return edit_material(teacher_id, material_id, {"status": status})


def create_activity(teacher_id: str, program_id: str, body: dict) -> dict:
    owned_program(teacher_id, program_id); _validate_title(body)
    activity = create_activity_row(program_id, teacher_id, {**body, "status": "published"})
    from models.enrollment_repository import list_student_ids_for_class
    from models.program_class_repository import class_ids_for_program
    from services.notification_service import notify
    student_ids = set()
    for class_id in class_ids_for_program(program_id):
        student_ids.update(list_student_ids_for_class(class_id))
    for student_id in student_ids:
        notify(student_id, "activity", "New activity published", activity.get("title", "A new activity is ready"), activity["id"])
    return activity


def edit_activity(teacher_id: str, activity_id: str, body: dict) -> dict:
    row = find_activity(activity_id)
    if not row: raise ValueError("NOT_FOUND")
    owned_program(teacher_id, row["programId"])
    if "title" in body: _validate_title(body)
    return update_activity_row(activity_id, body) or row


def set_activity_status(teacher_id: str, activity_id: str, status: str) -> dict:
    if status not in {"draft", "published", "closed"}: raise ValueError("INVALID_STATUS")
    previous = find_activity(activity_id)
    activity = edit_activity(teacher_id, activity_id, {"status": status})
    if status == "published" and previous and previous.get("status") != "published":
        from models.enrollment_repository import list_student_ids_for_class
        from models.program_class_repository import class_ids_for_program
        from services.notification_service import notify
        student_ids = set()
        for class_id in class_ids_for_program(activity["programId"]):
            student_ids.update(list_student_ids_for_class(class_id))
        for student_id in student_ids:
            notify(student_id, "activity", "New activity published", activity.get("title", "A new activity is ready"), activity_id)
    return activity
