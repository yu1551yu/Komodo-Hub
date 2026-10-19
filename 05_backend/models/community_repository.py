from __future__ import annotations

from models.json_store import now_iso, read_rows, write_rows
from models.work_repository import create_row, find_row, update_row
from models.user_repository import find_by_id

ORGANISATIONS = "community_organisations.json"
MEMBERSHIPS = "community_memberships.json"
JOIN_REQUESTS = "community_join_requests.json"


def seed_community_if_empty() -> None:
    if not read_rows(ORGANISATIONS):
        write_rows(
            ORGANISATIONS,
            [
                {
                    "id": "org_demo_reef",
                    "name": "Flores Reef Guardians",
                    "bio": "Local volunteers coordinating reef clean-ups, sightings and school outreach around Labuan Bajo.",
                    "region": "East Nusa Tenggara",
                    "status": "approved",
                    "createdAt": "2026-10-01T00:00:00+00:00",
                    "updatedAt": "2026-10-01T00:00:00+00:00",
                }
            ],
        )
    org_ids = {row.get("id") for row in read_rows(ORGANISATIONS)}
    demo_users_exist = find_by_id("usr_demo_community_admin") and find_by_id("usr_demo_public")
    if not read_rows(MEMBERSHIPS) and "org_demo_reef" in org_ids and demo_users_exist:
        write_rows(
            MEMBERSHIPS,
            [
                {
                    "id": "mem_demo_admin",
                    "organisationId": "org_demo_reef",
                    "userId": "usr_demo_community_admin",
                    "role": "OWNER",
                    "status": "active",
                    "createdAt": "2026-10-01T00:00:00+00:00",
                    "updatedAt": "2026-10-01T00:00:00+00:00",
                },
                {
                    "id": "mem_demo_member",
                    "organisationId": "org_demo_reef",
                    "userId": "usr_demo_public",
                    "role": "MEMBER",
                    "status": "active",
                    "createdAt": "2026-10-01T00:00:00+00:00",
                    "updatedAt": "2026-10-01T00:00:00+00:00",
                },
            ],
        )


def list_organisations() -> list[dict]:
    seed_community_if_empty()
    return [row for row in read_rows(ORGANISATIONS) if row.get("status") == "approved"]


def find_organisation(organisation_id: str) -> dict | None:
    seed_community_if_empty()
    return find_row(ORGANISATIONS, organisation_id)


def create_organisation(values: dict) -> dict:
    seed_community_if_empty()
    name = str(values.get("name") or "").strip()
    if len(name) < 2:
        raise ValueError("INVALID_NAME")
    rows = read_rows(ORGANISATIONS)
    if any(str(row.get("name", "")).lower() == name.lower() for row in rows):
        raise ValueError("DUPLICATE_ORGANISATION")
    return create_row(
        ORGANISATIONS,
        "org",
        {
            "name": name,
            "bio": str(values.get("bio") or "").strip(),
            "region": str(values.get("region") or "").strip(),
            "status": "approved",
        },
    )


def memberships_for_user(user_id: str) -> list[dict]:
    seed_community_if_empty()
    orgs = {row["id"]: row for row in read_rows(ORGANISATIONS)}
    rows = []
    for membership in read_rows(MEMBERSHIPS):
        if membership.get("userId") == user_id and membership.get("status") == "active":
            org = orgs.get(membership.get("organisationId"))
            if org and org.get("status") == "approved":
                rows.append({**membership, "organisation": org})
    return rows


def members_for_org(organisation_id: str) -> list[dict]:
    seed_community_if_empty()
    return [
        row
        for row in read_rows(MEMBERSHIPS)
        if row.get("organisationId") == organisation_id and row.get("status") == "active"
    ]


def find_membership(user_id: str, organisation_id: str) -> dict | None:
    return next(
        (
            row
            for row in memberships_for_user(user_id)
            if row.get("organisationId") == organisation_id
        ),
        None,
    )


def create_membership(user_id: str, organisation_id: str, role: str = "MEMBER") -> dict:
    user = find_by_id(user_id)
    if not user or user.get("role") != "PUBLIC":
        raise ValueError("FORBIDDEN")
    existing = find_membership(user_id, organisation_id)
    if existing:
        return existing
    if not find_row(ORGANISATIONS, organisation_id):
        raise ValueError("NOT_FOUND")
    return create_row(
        MEMBERSHIPS,
        "mem",
        {
            "organisationId": organisation_id,
            "userId": user_id,
            "role": role,
            "status": "active",
        },
    )


def join_request_for_user(user_id: str, organisation_id: str) -> dict | None:
    rows = [row for row in read_rows(JOIN_REQUESTS) if row.get("userId") == user_id and row.get("organisationId") == organisation_id]
    return max(rows, key=lambda row: row.get("createdAt", ""), default=None)


def create_join_request(user_id: str, organisation_id: str, note: str) -> dict:
    if find_membership(user_id, organisation_id):
        raise ValueError("ALREADY_MEMBER")
    existing = join_request_for_user(user_id, organisation_id)
    if existing and existing.get("status") == "pending":
        raise ValueError("DUPLICATE_REQUEST")
    if not find_organisation(organisation_id):
        raise ValueError("NOT_FOUND")
    return create_row(JOIN_REQUESTS, "joinreq", {"organisationId": organisation_id, "userId": user_id, "note": note, "status": "pending", "reviewedBy": None, "reviewedAt": None})


def requests_for_org(organisation_id: str) -> list[dict]:
    return sorted([row for row in read_rows(JOIN_REQUESTS) if row.get("organisationId") == organisation_id], key=lambda row: row.get("createdAt", ""), reverse=True)


def review_join_request(actor_id: str, request_id: str, decision: str) -> tuple[dict, dict | None]:
    if decision not in {"approved", "rejected"}:
        raise ValueError("INVALID_STATUS")
    request = find_row(JOIN_REQUESTS, request_id)
    if not request:
        raise ValueError("NOT_FOUND")
    admin = find_membership(actor_id, request.get("organisationId", ""))
    if not admin or admin.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    if request.get("status") != "pending":
        raise ValueError("ALREADY_REVIEWED")
    membership = create_membership(request["userId"], request["organisationId"], "MEMBER") if decision == "approved" else None
    updated = update_row(JOIN_REQUESTS, request_id, {"status": decision, "reviewedBy": actor_id, "reviewedAt": now_iso()}, {"status", "reviewedBy", "reviewedAt"}) or request
    return updated, membership


def deactivate_membership(actor_id: str, membership_id: str) -> dict:
    target = find_row(MEMBERSHIPS, membership_id)
    if not target:
        raise ValueError("NOT_FOUND")
    actor_membership = find_membership(actor_id, target.get("organisationId", ""))
    if not actor_membership or actor_membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    if target.get("userId") == actor_id:
        raise ValueError("FORBIDDEN")
    if target.get("role") == "OWNER" or (actor_membership.get("role") == "ADMIN" and target.get("role") != "MEMBER"):
        raise ValueError("FORBIDDEN")
    return update_row(MEMBERSHIPS, membership_id, {"status": "inactive", "updatedAt": now_iso()}, {"status", "updatedAt"}) or target


def update_membership_role(actor_id: str, membership_id: str, role: str) -> dict:
    if role not in {"MEMBER", "ADMIN"}:
        raise ValueError("INVALID_ROLE")
    target = find_row(MEMBERSHIPS, membership_id)
    if not target:
        raise ValueError("NOT_FOUND")
    actor_membership = find_membership(actor_id, target.get("organisationId", ""))
    if not actor_membership or actor_membership.get("role") != "OWNER":
        raise ValueError("FORBIDDEN")
    if target.get("role") == "OWNER" or target.get("userId") == actor_id:
        raise ValueError("FORBIDDEN")
    return update_row(MEMBERSHIPS, membership_id, {"role": role}, {"role"}) or target
