from __future__ import annotations

from models.community_repository import find_membership, find_organisation
from models.contribution_repository import create_contribution, find_contribution, list_for_author, list_published
from models.user_repository import find_by_id
from models.contribution_comment_repository import create_comment, list_for_contribution, list_for_contributions, mark_read


def _shape(row: dict) -> dict:
    author = find_by_id(row.get("authorId", "")) or {}
    organisation_id = row.get("organisationId")
    org = find_organisation(organisation_id) if organisation_id else None
    return {
        "id": row.get("id"),
        "title": row.get("title", ""),
        "body": row.get("body", ""),
        "type": row.get("type", ""),
        "createdAt": row.get("createdAt"),
        "updatedAt": row.get("updatedAt"),
        "author": _public_author(author, row.get("authorId")),
        "community": {"id": organisation_id, "name": org.get("name", "Organization")} if org else None,
        "libraryStatus": row.get("libraryStatus", "approved" if org else None),
        "reviewReason": row.get("reviewReason", ""),
    }


def _public_author(user: dict, user_id: str | None) -> dict:
    if user.get("role") == "STUDENT":
        return {"name": "Student naturalist", "isStudent": True}
    profile = user.get("accountProfile") if isinstance(user.get("accountProfile"), dict) else {}
    return {"id": user_id, "name": user.get("name", "Community member"), "avatarId": profile.get("avatarId", "")}


def _shape_comment(row: dict) -> dict:
    author = find_by_id(row.get("authorId", "")) or {}
    return {
        "id": row.get("id"),
        "contributionId": row.get("contributionId"),
        "content": row.get("content", ""),
        "createdAt": row.get("createdAt"),
        "readByOwner": bool(row.get("readByOwner")),
        "author": _public_author(author, row.get("authorId")),
    }


def public_contributions(organisation_id: str | None = None) -> dict:
    return {"contributions": [_shape(row) for row in list_published(organisation_id)]}


def contribution_detail(contribution_id: str) -> dict:
    row = find_contribution(contribution_id)
    if not row:
        raise ValueError("NOT_FOUND")
    return {"contribution": _shape(row)}


def my_contributions(actor: dict) -> dict:
    return {"contributions": [_shape(row) for row in list_for_author(actor["id"])]}


def create(actor: dict, body: dict) -> dict:
    organisation_id = str(body.get("organisationId") or "").strip() or None
    if organisation_id and not find_membership(actor["id"], organisation_id):
        raise ValueError("FORBIDDEN")
    row = create_contribution(actor["id"], organisation_id, body)
    return {"contribution": _shape(row)}


def contribution_comments(contribution_id: str) -> dict:
    if not find_contribution(contribution_id):
        raise ValueError("NOT_FOUND")
    return {"comments": [_shape_comment(row) for row in list_for_contribution(contribution_id)]}


def add_comment(actor: dict, contribution_id: str, body: dict) -> dict:
    if not find_contribution(contribution_id):
        raise ValueError("NOT_FOUND")
    row = create_comment(contribution_id, actor["id"], body.get("content"))
    return {"comment": _shape_comment(row)}


def received_comments(actor: dict) -> dict:
    contributions = list_for_author(actor["id"])
    by_id = {row["id"]: row for row in contributions}
    rows = []
    for comment in list_for_contributions(set(by_id)):
        contribution = by_id[comment["contributionId"]]
        rows.append({**_shape_comment(comment), "contribution": {"id": contribution["id"], "title": contribution.get("title", ""), "type": contribution.get("type", "article")}})
    return {"comments": rows, "unreadCount": sum(not row["readByOwner"] for row in rows)}


def read_comment(actor: dict, comment_id: str) -> dict:
    comment = next((row for row in list_for_contributions({row["id"] for row in list_for_author(actor["id"])}) if row.get("id") == comment_id), None)
    if not comment:
        raise ValueError("NOT_FOUND")
    return {"comment": _shape_comment(mark_read(comment_id) or comment)}
