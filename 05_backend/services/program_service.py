from __future__ import annotations

from models.class_repository import public_class
from models.enrollment_repository import list_for_student
from models.learning_activity_repository import list_for_program as list_activities
from models.material_repository import list_for_program as list_materials
from models.program_class_repository import class_ids_for_program, program_ids_for_classes, replace_assignments
from models.program_repository import create, find_by_id, list_by_teacher, update
from services.ownership_service import owned_class, owned_program

PROGRAM_STATUSES = {"draft", "published", "archived"}


def enriched_program(row: dict) -> dict:
    return {**row, "classIds": class_ids_for_program(row["id"])}


def teacher_programs(teacher_id: str) -> list[dict]:
    return [enriched_program(row) for row in list_by_teacher(teacher_id)]


def teacher_program(teacher_id: str, program_id: str) -> dict:
    row = owned_program(teacher_id, program_id)
    return {**enriched_program(row), "materials": list_materials(program_id), "activities": list_activities(program_id)}


def create_program(teacher_id: str, body: dict) -> dict:
    if len(str(body.get("title") or "").strip()) < 2:
        raise ValueError("INVALID_TITLE")
    class_ids = list(dict.fromkeys(str(value) for value in body.get("classIds", []) if value))
    for class_id in class_ids:
        owned_class(teacher_id, class_id)
    program = create(teacher_id, body)
    replace_assignments(program["id"], class_ids)
    program = update(program["id"], {"status": "published"}) or program
    from models.enrollment_repository import list_student_ids_for_class
    from services.notification_service import notify
    student_ids = set()
    for class_id in class_ids:
        student_ids.update(list_student_ids_for_class(class_id))
    for student_id in student_ids:
        notify(student_id, "program", "New program assigned", program.get("title", "A new program is ready"), program["id"])
    return enriched_program(program)


def edit_program(teacher_id: str, program_id: str, body: dict) -> dict:
    owned_program(teacher_id, program_id)
    patch = {key: str(body.get(key) or "").strip() for key in ("title", "description", "learningObjectives") if key in body}
    if "title" in patch and len(patch["title"]) < 2:
        raise ValueError("INVALID_TITLE")
    if not patch:
        raise ValueError("EMPTY_PATCH")
    return enriched_program(update(program_id, patch) or {})


def set_program_status(teacher_id: str, program_id: str, status: str) -> dict:
    previous = owned_program(teacher_id, program_id)
    if status not in PROGRAM_STATUSES:
        raise ValueError("INVALID_STATUS")
    program = enriched_program(update(program_id, {"status": status}) or {})
    if status == "published" and previous.get("status") != "published":
        from models.enrollment_repository import list_student_ids_for_class
        from services.notification_service import notify
        student_ids = set()
        for class_id in class_ids_for_program(program_id):
            student_ids.update(list_student_ids_for_class(class_id))
        for student_id in student_ids:
            notify(student_id, "program", "New program assigned", program.get("title", "A new program is ready"), program_id)
    return program


def assign_classes(teacher_id: str, program_id: str, class_ids: list[str]) -> dict:
    program = owned_program(teacher_id, program_id)
    previous_ids = set(class_ids_for_program(program_id))
    clean_ids = list(dict.fromkeys(str(value) for value in class_ids))
    for class_id in clean_ids:
        owned_class(teacher_id, class_id)
    replace_assignments(program_id, clean_ids)
    if program.get("status") == "published":
        from models.enrollment_repository import list_student_ids_for_class
        from services.notification_service import notify
        student_ids = set()
        for class_id in set(clean_ids) - previous_ids:
            student_ids.update(list_student_ids_for_class(class_id))
        for student_id in student_ids:
            notify(student_id, "program", "New program assigned", program.get("title", "A new program is ready"), program_id)
    return enriched_program(program)


def student_program_ids(student_id: str) -> list[str]:
    class_ids = [row["classId"] for row in list_for_student(student_id)]
    return program_ids_for_classes(class_ids)


def student_programs(student_id: str) -> list[dict]:
    rows = []
    for program_id in student_program_ids(student_id):
        row = find_by_id(program_id)
        if row and row.get("status") == "published":
            rows.append(enriched_program(row))
    return rows


def student_program(student_id: str, program_id: str) -> dict:
    if program_id not in student_program_ids(student_id):
        raise ValueError("FORBIDDEN")
    row = find_by_id(program_id)
    if not row or row.get("status") != "published":
        raise ValueError("NOT_FOUND")
    return {
        **enriched_program(row),
        "materials": [item for item in list_materials(program_id) if item.get("status") == "published"],
        "activities": [item for item in list_activities(program_id) if item.get("status") == "published"],
    }
