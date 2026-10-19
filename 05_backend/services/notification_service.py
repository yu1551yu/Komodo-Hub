from __future__ import annotations

from models.work_repository import create_row, list_rows, update_row

FILE = "notifications.json"


def notify(user_id: str, kind: str, title: str, message: str, resource_id: str | None = None) -> dict:
    return create_row(FILE, "notice", {
        "userId": user_id,
        "kind": kind,
        "title": title,
        "message": message,
        "resourceId": resource_id,
        "readAt": None,
    })


def notifications_for(user_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("userId") == user_id],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def mark_read(user_id: str, notification_id: str | None = None, kind: str | None = None) -> int:
    from models.json_store import now_iso

    count = 0
    for row in list_rows(FILE):
        if row.get("userId") != user_id or row.get("readAt"):
            continue
        if notification_id and row.get("id") != notification_id:
            continue
        if kind and row.get("kind") != kind:
            continue
        update_row(FILE, row["id"], {"readAt": now_iso()}, {"readAt"})
        count += 1
    return count
