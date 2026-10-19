from __future__ import annotations

from models.json_store import new_id, now_iso, read_rows, write_rows

FILE = "programs.json"


def list_by_teacher(teacher_id: str) -> list[dict]:
    return [row for row in read_rows(FILE) if row.get("teacherId") == teacher_id]


def find_by_id(program_id: str) -> dict | None:
    return next((row for row in read_rows(FILE) if row.get("id") == program_id), None)


def create(teacher_id: str, body: dict) -> dict:
    now = now_iso()
    row = {
        "id": new_id("prg"), "title": str(body.get("title") or "").strip(),
        "description": str(body.get("description") or "").strip(),
        "learningObjectives": str(body.get("learningObjectives") or "").strip(),
        "teacherId": teacher_id, "status": "draft", "createdAt": now, "updatedAt": now,
    }
    rows = read_rows(FILE); rows.append(row); write_rows(FILE, rows)
    return row


def update(program_id: str, patch: dict) -> dict | None:
    rows = read_rows(FILE)
    for index, row in enumerate(rows):
        if row.get("id") == program_id:
            allowed = {key: patch[key] for key in ("title", "description", "learningObjectives", "status") if key in patch}
            rows[index] = {**row, **allowed, "updatedAt": now_iso()}
            write_rows(FILE, rows); return rows[index]
    return None
