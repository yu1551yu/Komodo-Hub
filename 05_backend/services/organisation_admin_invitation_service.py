from __future__ import annotations

from models.json_store import now_iso, read_rows, write_rows
from models.work_repository import create_row, find_row, update_row
from models.community_repository import MEMBERSHIPS, find_organisation
from models.user_repository import find_by_id
from services.notification_service import notify

FILE = "organisation_admin_invitations.json"


def invite(actor: dict, organisation_id: str, user_id: str) -> dict:
    if actor.get("role") != "ADMIN":
        raise ValueError("FORBIDDEN")
    org, user = find_organisation(organisation_id), find_by_id(user_id)
    if not org:
        raise ValueError("NOT_FOUND")
    if not user or user.get("role") != "PUBLIC":
        raise ValueError("ADMIN_USER_NOT_FOUND")
    pending = next((row for row in read_rows(FILE) if row.get("organisationId") == organisation_id and row.get("userId") == user_id and row.get("status") == "PENDING"), None)
    if pending:
        raise ValueError("DUPLICATE_INVITATION")
    invitation = create_row(FILE, "orginvite", {"organisationId": organisation_id, "userId": user_id, "invitedBy": actor["id"], "status": "PENDING", "respondedAt": None})
    notification = notify(user_id, "organization_admin_invitation", "Organization administrator invitation", f"You have been invited to manage {org['name']}.", invitation["id"])
    return {"invitation": invitation, "notification": notification}


def mine(actor: dict) -> dict:
    invitations = []
    for row in read_rows(FILE):
        if row.get("userId") != actor.get("id"):
            continue
        org = find_organisation(row.get("organisationId", ""))
        invitations.append({**row, "organisation": {"id": org.get("id"), "name": org.get("name"), "bio": org.get("bio"), "region": org.get("region")} if org else None})
    return {"invitations": sorted(invitations, key=lambda row: row.get("createdAt", ""), reverse=True)}


def respond(actor: dict, invitation_id: str, decision: str) -> dict:
    invitation = find_row(FILE, invitation_id)
    if not invitation:
        raise ValueError("NOT_FOUND")
    if invitation.get("userId") != actor.get("id"):
        raise ValueError("FORBIDDEN")
    if invitation.get("status") != "PENDING":
        raise ValueError("ALREADY_REVIEWED")
    normalized = decision.upper()
    if normalized not in {"ACCEPTED", "REJECTED"}:
        raise ValueError("VALIDATION_ERROR")
    membership = None
    if normalized == "ACCEPTED":
        rows, now, target = read_rows(MEMBERSHIPS), now_iso(), None
        for row in rows:
            if row.get("organisationId") != invitation["organisationId"]:
                continue
            if row.get("status") == "active" and row.get("role") == "OWNER":
                row["role"], row["updatedAt"] = "MEMBER", now
            if row.get("userId") == actor["id"]:
                target = row
        if target:
            target.update({"role": "OWNER", "status": "active", "updatedAt": now})
            membership = target
        else:
            from models.json_store import new_id
            membership = {"id": new_id("mem"), "organisationId": invitation["organisationId"], "userId": actor["id"], "role": "OWNER", "status": "active", "createdAt": now, "updatedAt": now}
            rows.append(membership)
        write_rows(MEMBERSHIPS, rows)
    updated = update_row(FILE, invitation_id, {"status": normalized, "respondedAt": now_iso()}, {"status", "respondedAt"})
    return {"invitation": updated, "membership": membership}
