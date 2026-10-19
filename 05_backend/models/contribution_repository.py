from __future__ import annotations

from html import escape

from models.work_repository import create_row, find_row, list_rows, update_row

FILE = "community_contributions.json"
ALLOWED_TYPES = {"article", "essay", "column"}


def sanitize_text(value: str, limit: int, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and len(text) < 2:
        raise ValueError("REQUIRED")
    if len(text) > limit:
        raise ValueError("TOO_LONG")
    return escape(text, quote=True)


def list_published(organisation_id: str | None = None) -> list[dict]:
    rows = [row for row in list_rows(FILE) if row.get("status") == "published"]
    if organisation_id:
        rows = [row for row in rows if row.get("organisationId") == organisation_id]
    return sorted(rows, key=lambda row: row.get("createdAt", ""), reverse=True)


def list_for_organisation_review(organisation_id: str) -> list[dict]:
    return sorted([row for row in list_rows(FILE) if row.get("organisationId") == organisation_id], key=lambda row: row.get("createdAt", ""), reverse=True)


def update_library_review(contribution_id: str, values: dict) -> dict | None:
    return update_row(FILE, contribution_id, values, {"libraryStatus", "reviewReason", "reviewedBy", "reviewedAt"})


def list_for_author(author_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("authorId") == author_id],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def find_contribution(contribution_id: str) -> dict | None:
    key = str(contribution_id or "").strip()
    if not key or "/" in key or "\\" in key:
        raise ValueError("INVALID_ID")
    row = find_row(FILE, key)
    if row and row.get("status") == "published":
        return row
    return None


def create_contribution(author_id: str, organisation_id: str | None, body: dict) -> dict:
    kind = str(body.get("type") or "").strip().lower()
    if kind not in ALLOWED_TYPES:
        raise ValueError("INVALID_TYPE")
    return create_row(
        FILE,
        "contrib",
        {
            "title": sanitize_text(body.get("title"), 160, True),
            "body": sanitize_text(body.get("body"), 12000, True),
            "type": kind,
            "authorId": author_id,
            "organisationId": organisation_id,
            "status": "published",
            "libraryStatus": "pending" if organisation_id else None,
            "reviewReason": "",
            "reviewedBy": None,
            "reviewedAt": None,
        },
    )
