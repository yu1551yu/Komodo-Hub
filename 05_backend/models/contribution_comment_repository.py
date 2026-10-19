from __future__ import annotations

from html import escape

from models.work_repository import create_row, find_row, list_rows, update_row

FILE = "contribution_comments.json"


def list_for_contribution(contribution_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("contributionId") == contribution_id],
        key=lambda row: row.get("createdAt", ""),
    )


def list_for_contributions(contribution_ids: set[str]) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("contributionId") in contribution_ids],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def create_comment(contribution_id: str, author_id: str, content: str) -> dict:
    value = str(content or "").strip()
    if len(value) < 1 or len(value) > 1000:
        raise ValueError("VALIDATION_ERROR")
    return create_row(FILE, "contribcomment", {
        "contributionId": contribution_id,
        "authorId": author_id,
        "content": escape(value, quote=True),
        "readByOwner": False,
    })


def mark_read(comment_id: str) -> dict | None:
    if not find_row(FILE, comment_id):
        return None
    return update_row(FILE, comment_id, {"readByOwner": True}, {"readByOwner"})
