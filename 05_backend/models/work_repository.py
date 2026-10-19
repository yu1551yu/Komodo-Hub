from __future__ import annotations

from models.json_store import new_id, now_iso, read_rows, write_rows


def list_rows(file_name: str) -> list[dict]:
    return read_rows(file_name)


def find_row(file_name: str, row_id: str) -> dict | None:
    return next((row for row in read_rows(file_name) if row.get("id") == row_id), None)


def create_row(file_name: str, prefix: str, values: dict) -> dict:
    rows = read_rows(file_name)
    now = now_iso()
    row = {"id": new_id(prefix), **values, "createdAt": now, "updatedAt": now}
    rows.append(row)
    write_rows(file_name, rows)
    return row


def update_row(file_name: str, row_id: str, patch: dict, allowed: set[str]) -> dict | None:
    rows = read_rows(file_name)
    for index, row in enumerate(rows):
        if row.get("id") == row_id:
            clean = {key: value for key, value in patch.items() if key in allowed}
            rows[index] = {**row, **clean, "updatedAt": now_iso()}
            write_rows(file_name, rows)
            return rows[index]
    return None


def delete_row(file_name: str, row_id: str) -> bool:
    rows = read_rows(file_name)
    remaining = [row for row in rows if row.get("id") != row_id]
    if len(remaining) == len(rows):
        return False
    write_rows(file_name, remaining)
    return True
