from __future__ import annotations

from models.community_repository import (
    create_organisation,
    create_membership,
    create_join_request,
    deactivate_membership,
    find_membership,
    find_organisation,
    join_request_for_user,
    list_organisations,
    members_for_org,
    memberships_for_user,
    requests_for_org,
    review_join_request,
    update_membership_role,
)
from models.user_repository import create_user, find_by_email, find_by_id, search_users
from models.json_store import new_id, now_iso, read_rows, write_rows
from models.community_repository import ORGANISATIONS
import base64
import binascii
from pathlib import Path

COVER_DIR = Path(__file__).resolve().parent.parent / "data" / "organization_covers"


def public_directory(actor: dict | None = None) -> dict:
    memberships = memberships_for_user(actor["id"]) if actor else []
    member_org_ids = {row["organisationId"] for row in memberships}
    return {
        "organisations": [
            {
                **org,
                "memberCount": len(members_for_org(org["id"])),
                "viewerMembership": next(
                    (row for row in memberships if row["organisationId"] == org["id"]),
                    None,
                ),
                "canJoin": bool(actor) and actor.get("role") == "PUBLIC" and org["id"] not in member_org_ids,
                "viewerJoinRequest": join_request_for_user(actor["id"], org["id"]) if actor else None,
            }
            for org in list_organisations()
        ],
        "viewerMemberships": memberships,
    }


def create_community(actor: dict, body: dict) -> dict:
    if actor.get("role") != "ADMIN":
        raise ValueError("FORBIDDEN")
    org = create_organisation(body)
    admin_email = str(body.get("adminEmail") or "").strip().lower()
    if admin_email:
        admin_user = find_by_email(admin_email)
        if not admin_user:
            raise ValueError("ADMIN_USER_NOT_FOUND")
        create_membership(admin_user["id"], org["id"], "ADMIN")
    return {"organisation": org}


def join_organisation(actor: dict, organisation_id: str, body: dict | None = None) -> dict:
    if actor.get("role") != "PUBLIC":
        raise ValueError("FORBIDDEN")
    note = str((body or {}).get("note") or "").strip()
    if len(note) > 1000:
        raise ValueError("VALIDATION_ERROR")
    request = create_join_request(actor["id"], organisation_id, note)
    return {"joinRequest": request, **public_directory(actor)}


def my_communities(actor: dict) -> dict:
    return {"memberships": memberships_for_user(actor["id"])}


def join_requests(actor: dict, organisation_id: str) -> dict:
    admin = find_membership(actor["id"], organisation_id)
    if not admin or admin.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    rows = []
    for request in requests_for_org(organisation_id):
        user = find_by_id(request.get("userId", "")) or {}
        rows.append({**request, "applicant": {"id": user.get("id"), "name": user.get("name", "Registered user"), "email": user.get("email", "")}})
    return {"joinRequests": rows}


def decide_join_request(actor: dict, request_id: str, status: str) -> dict:
    request_row = next((row for row in read_rows("community_join_requests.json") if row.get("id") == request_id), None)
    applicant = find_by_id(request_row.get("userId", "")) if request_row else None
    if applicant and applicant.get("role") != "PUBLIC":
        raise ValueError("FORBIDDEN")
    request, membership = review_join_request(actor["id"], request_id, status)
    return {"joinRequest": request, "membership": membership}


def member_candidates(actor: dict, organisation_id: str, query: str) -> dict:
    admin = find_membership(actor["id"], organisation_id)
    if not admin or admin.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    member_ids = {row.get("userId") for row in members_for_org(organisation_id)}
    users = [{"id": user.get("id"), "name": user.get("name"), "email": user.get("email"), "role": user.get("role")} for user in search_users(query) if user.get("id") not in member_ids and user.get("role") == "PUBLIC"]
    return {"users": users}


def organisation_workspace(actor: dict, organisation_id: str) -> dict:
    membership = next(
        (row for row in memberships_for_user(actor["id"]) if row["organisationId"] == organisation_id),
        None,
    )
    if not membership:
        raise ValueError("FORBIDDEN")
    organisation = membership["organisation"]
    members = []
    for row in members_for_org(organisation_id):
        user = find_by_id(row.get("userId", "")) or {}
        members.append(
            {
                "id": row["id"],
                "userId": row.get("userId"),
                "name": user.get("name", "Community member"),
                "role": row.get("role", "MEMBER"),
                "joinedAt": row.get("createdAt"),
            }
        )
    return {
        "organisation": organisation,
        "viewerMembership": membership,
        "members": members,
        "permissions": {
            "canManageMembers": membership.get("role") in {"OWNER", "ADMIN"},
            "canManageAdministrators": membership.get("role") == "OWNER",
            "canPublishResources": membership.get("role") in {"ADMIN", "MEMBER"},
        },
    }


def update_organisation_profile(actor: dict, organisation_id: str, body: dict) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    rows = read_rows(ORGANISATIONS)
    index = next((i for i, row in enumerate(rows) if row.get("id") == organisation_id), None)
    if index is None:
        raise ValueError("NOT_FOUND")
    name = str(body.get("name", rows[index].get("name", ""))).strip()
    if len(name) < 2:
        raise ValueError("VALIDATION_ERROR")
    rows[index] = {**rows[index], "name": name, "bio": str(body.get("bio", rows[index].get("bio", ""))).strip(), "region": str(body.get("region", rows[index].get("region", ""))).strip(), "logoUrl": str(body.get("logoUrl", rows[index].get("logoUrl", ""))).strip(), "contactEmail": str(body.get("contactEmail", rows[index].get("contactEmail", ""))).strip(), "website": str(body.get("website", rows[index].get("website", ""))).strip(), "updatedAt": now_iso()}
    write_rows(ORGANISATIONS, rows)
    return {"organisation": rows[index]}


def upload_organisation_cover(actor: dict, organisation_id: str, body: dict) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    content_type = str(body.get("contentType") or "").lower()
    if content_type == "image/jpg": content_type = "image/jpeg"
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type)
    if not suffix: raise ValueError("INVALID_IMAGE")
    try: data = base64.b64decode(str(body.get("imageBase64") or ""), validate=True)
    except (binascii.Error, ValueError): raise ValueError("INVALID_IMAGE")
    if not data or len(data) > 5 * 1024 * 1024: raise ValueError("IMAGE_SIZE")
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    for old_suffix in (".jpg", ".png", ".webp"):
        (COVER_DIR / f"{organisation_id}{old_suffix}").unlink(missing_ok=True)
    (COVER_DIR / f"{organisation_id}{suffix}").write_bytes(data)
    rows = read_rows(ORGANISATIONS); index = next(i for i, row in enumerate(rows) if row.get("id") == organisation_id)
    rows[index]["coverImageUrl"] = f"/api/community/organisations/{organisation_id}/cover?v={new_id('img')}"; rows[index]["updatedAt"] = now_iso(); write_rows(ORGANISATIONS, rows)
    return {"organisation": rows[index], "coverImageUrl": rows[index]["coverImageUrl"]}


def remove_organisation_cover(actor: dict, organisation_id: str) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    rows = read_rows(ORGANISATIONS)
    index = next((i for i, row in enumerate(rows) if row.get("id") == organisation_id), None)
    if index is None:
        raise ValueError("NOT_FOUND")
    for suffix in (".jpg", ".png", ".webp"):
        (COVER_DIR / f"{organisation_id}{suffix}").unlink(missing_ok=True)
    rows[index].pop("coverImageUrl", None)
    rows[index]["updatedAt"] = now_iso()
    write_rows(ORGANISATIONS, rows)
    return {"organisation": rows[index], "coverImageUrl": None}


def organisation_cover(organisation_id: str):
    for suffix, content_type in ((".jpg", "image/jpeg"), (".png", "image/png"), (".webp", "image/webp")):
        path = COVER_DIR / f"{organisation_id}{suffix}"
        if path.is_file(): return path.read_bytes(), content_type
    return None, None


def organisation_members(actor: dict | None, organisation_id: str) -> dict:
    org = find_organisation(organisation_id)
    if not org or org.get("status") != "approved":
        raise ValueError("NOT_FOUND")
    membership = find_membership(actor["id"], organisation_id) if actor else None
    if not membership:
        raise ValueError("FORBIDDEN")
    members = []
    for row in members_for_org(organisation_id):
        user = find_by_id(row.get("userId", "")) or {}
        members.append(
            {
                "id": row["id"],
                "userId": row.get("userId"),
                "name": user.get("name", "Community member"),
                "email": user.get("email", ""),
                "role": row.get("role", "MEMBER"),
                "joinedAt": row.get("createdAt"),
            }
        )
    return {"organisation": org, "viewerMembership": membership, "members": members}


def add_member(actor: dict, organisation_id: str, body: dict) -> dict:
    admin_membership = find_membership(actor["id"], organisation_id)
    if not admin_membership or admin_membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    user_id = str(body.get("userId") or "").strip()
    if user_id:
        user = find_by_id(user_id)
        if not user or user.get("role") != "PUBLIC":
            raise ValueError("NOT_FOUND")
        membership = create_membership(user["id"], organisation_id, "MEMBER")
        return {"member": membership, "user": {"id": user["id"], "name": user["name"], "email": user.get("email", "")}, "createdUser": False}
    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if len(name) < 2 or "@" not in email:
        raise ValueError("VALIDATION_ERROR")
    user = find_by_email(email)
    created_user = False
    if not user:
        if len(password) < 6:
            raise ValueError("PASSWORD_REQUIRED")
        user = create_user(name, email, password, "PUBLIC", extra={"publicProfile": {"location": "", "interestSpecies": []}})
        created_user = True
    membership = create_membership(user["id"], organisation_id, "MEMBER")
    return {"member": membership, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}, "createdUser": created_user}


def change_member_role(actor: dict, membership_id: str, role: str) -> dict:
    updated = update_membership_role(actor["id"], membership_id, role)
    return {"membership": updated}


def remove_member(actor: dict, membership_id: str) -> dict:
    updated = deactivate_membership(actor["id"], membership_id)
    return {"membership": updated}
