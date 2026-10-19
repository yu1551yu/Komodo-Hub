from __future__ import annotations

from models.json_store import new_id, now_iso, read_rows, write_rows

FILE = "program_classes.json"


def class_ids_for_program(program_id: str) -> list[str]:
    return [row["classId"] for row in read_rows(FILE) if row.get("programId") == program_id]


def program_ids_for_classes(class_ids: list[str]) -> list[str]:
    wanted = set(class_ids)
    return list(dict.fromkeys(row["programId"] for row in read_rows(FILE) if row.get("classId") in wanted))


def replace_assignments(program_id: str, class_ids: list[str]) -> list[str]:
    rows = [row for row in read_rows(FILE) if row.get("programId") != program_id]
    for class_id in dict.fromkeys(class_ids):
        rows.append({"id": new_id("pc"), "programId": program_id, "classId": class_id, "assignedAt": now_iso()})
    write_rows(FILE, rows)
    return class_ids
