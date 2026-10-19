from __future__ import annotations

from models.json_store import new_id, now_iso, read_rows, write_rows

FILE = "learning_activities.json"


def list_for_program(program_id: str) -> list[dict]:
    return [row for row in read_rows(FILE) if row.get("programId") == program_id]


def find_by_id(activity_id: str) -> dict | None:
    return next((row for row in read_rows(FILE) if row.get("id") == activity_id), None)


def create(program_id: str, teacher_id: str, body: dict) -> dict:
    now = now_iso(); rows = read_rows(FILE)
    row = {"id": new_id("lact"), "programId": program_id, "title": str(body.get("title") or "").strip(), "description": str(body.get("description") or "").strip(), "instructions": str(body.get("instructions") or "").strip(), "activityType": str(body.get("activityType") or "classroom"), "dueDate": body.get("dueDate") or None, "attachments": body.get("attachments") if isinstance(body.get("attachments"), list) else [], "status": str(body.get("status") or "published"), "createdBy": teacher_id, "createdAt": now, "updatedAt": now}
    rows.append(row); write_rows(FILE, rows); return row


def update(activity_id: str, patch: dict) -> dict | None:
    rows = read_rows(FILE)
    for index, row in enumerate(rows):
        if row.get("id") == activity_id:
            allowed = {key: patch[key] for key in ("title", "description", "instructions", "activityType", "dueDate", "attachments", "status") if key in patch}
            rows[index] = {**row, **allowed, "updatedAt": now_iso()}; write_rows(FILE, rows); return rows[index]
    return None
