from __future__ import annotations

from models.json_store import now_iso, read_rows, write_rows
from models.work_repository import create_row
from models.user_repository import find_by_id, search_users
from models.community_repository import ORGANISATIONS, MEMBERSHIPS, find_organisation, members_for_org
from models.conservation_program_repository import enrollments_for_organisation
from services.community_library_service import community_library
from services.organisation_admin_invitation_service import invite

AUDIT = "admin_audit_log.json"


def _require_admin(actor: dict) -> None:
    if actor.get("role") != "ADMIN":
        raise ValueError("FORBIDDEN")


def _administrator(organisation_id: str) -> dict | None:
    membership = next((row for row in members_for_org(organisation_id) if row.get("role") == "OWNER"), None) or next((row for row in members_for_org(organisation_id) if row.get("role") == "ADMIN"), None)
    if not membership:
        return None
    user = find_by_id(membership.get("userId", "")) or {}
    return {"membershipId": membership.get("id"), "id": user.get("id"), "name": user.get("name", "Registered user"), "email": user.get("email", "")}


def _summary(org: dict) -> dict:
    return {**org, "administrator": _administrator(org["id"]), "memberCount": len(members_for_org(org["id"])), "programCount": len({row.get("programId") for row in enrollments_for_organisation(org["id"])})}


def _audit(actor: dict, action: str, organisation_id: str, details: dict | None = None) -> None:
    create_row(AUDIT, "audit", {"actorId": actor["id"], "action": action, "organisationId": organisation_id, "details": details or {}})


def list_all(actor: dict, query: str = "", status: str = "") -> dict:
    _require_admin(actor)
    rows = read_rows(ORGANISATIONS)
    needle = query.strip().lower()
    if needle:
        rows = [row for row in rows if needle in f"{row.get('name', '')} {row.get('bio', '')} {row.get('region', '')}".lower()]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    shaped = [_summary(row) for row in sorted(rows, key=lambda row: row.get("createdAt", ""), reverse=True)]
    return {"organisations": shaped, "total": len(shaped)}


def stats(actor: dict) -> dict:
    _require_admin(actor)
    rows = read_rows(ORGANISATIONS)
    return {"total": len(rows), "active": sum(row.get("status") == "approved" for row in rows), "inactive": sum(row.get("status") != "approved" for row in rows), "members": sum(len(members_for_org(row["id"])) for row in rows)}


def detail(actor: dict, organisation_id: str) -> dict:
    _require_admin(actor)
    org = find_organisation(organisation_id)
    if not org:
        raise ValueError("NOT_FOUND")
    members = []
    for membership in members_for_org(organisation_id):
        user = find_by_id(membership.get("userId", "")) or {}
        members.append({"id": membership.get("id"), "userId": user.get("id"), "name": user.get("name", "Registered user"), "email": user.get("email", ""), "role": membership.get("role"), "joinedAt": membership.get("createdAt")})
    programs = list({row["program"]["id"]: row["program"] for row in enrollments_for_organisation(organisation_id) if row.get("program")}.values())
    library = community_library(organisation_id).get("items", []) if org.get("status") == "approved" else []
    return {"organisation": _summary(org), "members": members, "programs": programs, "library": library}


def create(actor: dict, body: dict) -> dict:
    _require_admin(actor)
    name = str(body.get("name") or "").strip()
    user_id = str(body.get("administratorUserId") or "").strip()
    user = find_by_id(user_id)
    if len(name) < 2:
        raise ValueError("VALIDATION_ERROR")
    if not user or user.get("role") != "PUBLIC":
        raise ValueError("ADMIN_USER_NOT_FOUND")
    orgs, memberships = read_rows(ORGANISATIONS), read_rows(MEMBERSHIPS)
    try:
        org = create_row(ORGANISATIONS, "org", {"name": name, "bio": str(body.get("description") or body.get("bio") or "").strip(), "region": str(body.get("location") or body.get("region") or "").strip(), "logoUrl": str(body.get("logoUrl") or "").strip(), "status": "approved"})
        invitation = invite(actor, org["id"], user_id)
    except Exception:
        write_rows(ORGANISATIONS, orgs); write_rows(MEMBERSHIPS, memberships)
        raise
    _audit(actor, "ORGANISATION_CREATED", org["id"], {"administratorUserId": user_id})
    return {"organisation": _summary(org), **invitation}


def update(actor: dict, organisation_id: str, body: dict) -> dict:
    _require_admin(actor)
    rows = read_rows(ORGANISATIONS)
    index = next((i for i, row in enumerate(rows) if row.get("id") == organisation_id), None)
    if index is None:
        raise ValueError("NOT_FOUND")
    patch = {"name": str(body.get("name") or rows[index].get("name") or "").strip(), "bio": str(body.get("description") if "description" in body else body.get("bio", rows[index].get("bio", ""))).strip(), "region": str(body.get("location") if "location" in body else body.get("region", rows[index].get("region", ""))).strip(), "logoUrl": str(body.get("logoUrl", rows[index].get("logoUrl", "")) or "").strip(), "updatedAt": now_iso()}
    if len(patch["name"]) < 2:
        raise ValueError("VALIDATION_ERROR")
    rows[index] = {**rows[index], **patch}; write_rows(ORGANISATIONS, rows)
    _audit(actor, "ORGANISATION_UPDATED", organisation_id)
    return {"organisation": _summary(rows[index])}


def set_status(actor: dict, organisation_id: str, status: str) -> dict:
    _require_admin(actor)
    normalized = "approved" if status.upper() == "ACTIVE" else "inactive" if status.upper() == "INACTIVE" else ""
    if not normalized:
        raise ValueError("VALIDATION_ERROR")
    rows = read_rows(ORGANISATIONS)
    index = next((i for i, row in enumerate(rows) if row.get("id") == organisation_id), None)
    if index is None: raise ValueError("NOT_FOUND")
    rows[index] = {**rows[index], "status": normalized, "updatedAt": now_iso()}; write_rows(ORGANISATIONS, rows)
    _audit(actor, "ORGANISATION_STATUS_CHANGED", organisation_id, {"status": normalized})
    return {"organisation": _summary(rows[index])}


def change_administrator(actor: dict, organisation_id: str, user_id: str) -> dict:
    _require_admin(actor)
    if not find_organisation(organisation_id): raise ValueError("NOT_FOUND")
    user = find_by_id(user_id)
    if not user or user.get("role") != "PUBLIC": raise ValueError("ADMIN_USER_NOT_FOUND")
    invitation = invite(actor, organisation_id, user_id)
    _audit(actor, "ORGANISATION_ADMIN_INVITED", organisation_id, {"newAdministratorUserId": user_id})
    return {**invitation, "administrator": _administrator(organisation_id)}


def user_search(actor: dict, query: str) -> dict:
    _require_admin(actor)
    return {"users": [{"id": row.get("id"), "name": row.get("name"), "email": row.get("email")} for row in search_users(query) if row.get("role") == "PUBLIC"][:20]}
