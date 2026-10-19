from __future__ import annotations

from models.json_store import new_id, now_iso, read_rows, write_rows

FILE = "materials.json"


def list_for_program(program_id: str) -> list[dict]:
    return sorted([row for row in read_rows(FILE) if row.get("programId") == program_id], key=lambda row: row.get("position", 0))


def find_by_id(material_id: str) -> dict | None:
    return next((row for row in read_rows(FILE) if row.get("id") == material_id), None)


def create(program_id: str, teacher_id: str, body: dict) -> dict:
    rows = read_rows(FILE); now = now_iso()
    row = {"id": new_id("mat"), "programId": program_id, "title": str(body.get("title") or "").strip(), "description": str(body.get("description") or body.get("content") or "").strip(), "resourceType": str(body.get("resourceType") or "teacher-note"), "resourceRef": str(body.get("resourceRef") or "").strip(), "sourceContentId": body.get("sourceContentId"), "attachments": body.get("attachments") if isinstance(body.get("attachments"), list) else [], "status": str(body.get("status") or "published"), "position": len([x for x in rows if x.get("programId") == program_id]), "createdBy": teacher_id, "createdAt": now, "updatedAt": now}
    rows.append(row); write_rows(FILE, rows); return row


def update(material_id: str, patch: dict) -> dict | None:
    rows = read_rows(FILE)
    target = next((row for row in rows if row.get("id") == material_id), None)
    if target and "position" in patch:
        siblings = sorted([row for row in rows if row.get("programId") == target.get("programId")], key=lambda row: row.get("position", 0))
        siblings = [row for row in siblings if row.get("id") != material_id]
        position = max(0, min(int(patch["position"]), len(siblings)))
        siblings.insert(position, target)
        positions = {row["id"]: index for index, row in enumerate(siblings)}
        for row in rows:
            if row.get("id") in positions:
                row["position"] = positions[row["id"]]
    for index, row in enumerate(rows):
        if row.get("id") == material_id:
            allowed = {key: patch[key] for key in ("title", "description", "resourceType", "resourceRef", "sourceContentId", "attachments", "status") if key in patch}
            rows[index] = {**row, **allowed, "updatedAt": now_iso()}; write_rows(FILE, rows); return rows[index]
    return None
