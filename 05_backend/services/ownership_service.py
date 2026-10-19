from __future__ import annotations

from models.class_repository import find_by_id as find_class


class OwnershipError(ValueError):
    pass


def owned_class(teacher_id: str, class_id: str) -> dict:
    row = find_class(class_id)
    if not row:
        raise OwnershipError("NOT_FOUND")
    if row.get("teacherId") != teacher_id:
        raise OwnershipError("FORBIDDEN")
    return row


def owned_program(teacher_id: str, program_id: str) -> dict:
    from models.program_repository import find_by_id

    row = find_by_id(program_id)
    if not row:
        raise OwnershipError("NOT_FOUND")
    if row.get("teacherId") != teacher_id:
        raise OwnershipError("FORBIDDEN")
    return row
