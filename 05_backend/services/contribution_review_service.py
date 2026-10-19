from __future__ import annotations

from models.json_store import now_iso
from models.community_repository import find_membership
from models.contribution_repository import find_contribution, list_for_organisation_review, update_library_review as update_contribution
from models.sighting_repository import find_sighting, list_for_organisation, update_library_review as update_sighting
from models.user_repository import find_by_id
from services.contribution_service import _shape as shape_contribution
from services.sighting_service import _shape as shape_sighting


def _require_admin(actor: dict, organisation_id: str) -> None:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")


def review_queue(actor: dict, organisation_id: str) -> dict:
    _require_admin(actor, organisation_id)
    items = []
    for row in list_for_organisation_review(organisation_id):
        author = find_by_id(row.get("authorId", "")) or {}
        items.append({**shape_contribution(row), "resourceType": "contribution", "contributor": {"id": author.get("id"), "name": author.get("name", "Member")}, "reviewedAt": row.get("reviewedAt")})
    for row in list_for_organisation(organisation_id):
        author = find_by_id(row.get("authorId", "")) or {}
        items.append({**shape_sighting(row), "resourceType": "sighting", "title": f"{shape_sighting(row).get('species', {}).get('name', 'Species')} sighting", "contributor": {"id": author.get("id"), "name": author.get("name", "Member")}, "reviewedAt": row.get("reviewedAt")})
    return {"items": sorted(items, key=lambda row: row.get("createdAt") or "", reverse=True)}


def review(actor: dict, organisation_id: str, resource_type: str, resource_id: str, decision: str, reason: str = "") -> dict:
    _require_admin(actor, organisation_id)
    normalized = decision.lower()
    if normalized not in {"approved", "rejected"}:
        raise ValueError("VALIDATION_ERROR")
    if normalized == "rejected" and len(reason.strip()) < 2:
        raise ValueError("REASON_REQUIRED")
    row = find_contribution(resource_id) if resource_type == "contribution" else find_sighting(resource_id) if resource_type == "sighting" else None
    if not row or row.get("organisationId") != organisation_id:
        raise ValueError("NOT_FOUND")
    values = {"libraryStatus": normalized, "reviewReason": reason.strip(), "reviewedBy": actor["id"], "reviewedAt": now_iso()}
    updated = update_contribution(resource_id, values) if resource_type == "contribution" else update_sighting(resource_id, values)
    return {"item": {"resourceType": resource_type, "id": resource_id, **values}, "saved": bool(updated)}
