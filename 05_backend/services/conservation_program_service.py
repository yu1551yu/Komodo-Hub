from __future__ import annotations

from models.community_repository import find_membership, members_for_org, memberships_for_user
from models.conservation_program_repository import (
    create_enrollment,
    enrollments_for_organisation,
    enrollments_for_program,
    enrollments_for_user,
    find_program,
    list_programs,
    create_program,
    update_program,
    applications_for_organisation,
    applications_for_user,
    create_program_application,
    find_program_application,
    update_program_application,
)
from models.user_repository import find_by_id
from models.json_store import now_iso


def _public_program(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row.get("title", ""),
        "summary": row.get("summary", ""),
        "description": row.get("description", ""),
        "participationInfo": row.get("participationInfo", ""),
        "region": row.get("region", ""),
        "allowedParticipantTypes": row.get("allowedParticipantTypes", []),
        "media": row.get("media") or {},
        "conservationGoal": row.get("conservationGoal") or row.get("summary", ""),
        "activities": row.get("activities") if isinstance(row.get("activities"), list) else [],
    }


def _with_viewer(program: dict, actor: dict | None) -> dict:
    row = _public_program(program)
    if actor:
        row["viewerEnrollment"] = next(
            (item for item in enrollments_for_user(actor["id"]) if item.get("programId") == program["id"]),
            None,
        )
    return row


def public_programs(actor: dict | None = None) -> dict:
    return {"programs": [_with_viewer(row, actor) for row in list_programs()]}


def program_detail(program_id: str, actor: dict | None = None) -> dict:
    program = find_program(program_id)
    if not program:
        raise ValueError("NOT_FOUND")
    shaped = _with_viewer(program, actor)
    shaped["participants"] = [
        {"name": (find_by_id(row.get("userId", "")) or {}).get("name", "Participant"), "source": row.get("source"), "organisationId": row.get("organisationId")}
        for row in enrollments_for_program(program_id)
    ]
    shaped["participantCount"] = len(shaped["participants"])
    return {"program": shaped}


def my_enrollments(actor: dict) -> dict:
    memberships = []
    for enrollment in enrollments_for_user(actor["id"]):
        memberships.append(_shape_enrollment(enrollment))
    org_rows = []
    for membership in memberships_for_user(actor["id"]):
        org_rows.extend(enrollments_for_organisation(membership["organisationId"]))
    return {"enrollments": memberships, "communityEnrollments": [_shape_enrollment(row) for row in org_rows], "applications": [_shape_application(row) for row in applications_for_user(actor["id"])]}


def apply_to_program(actor: dict, program_id: str, body: dict) -> dict:
    program = find_program(program_id)
    organisation_id = str(body.get("organisationId") or "").strip()
    note = str(body.get("note") or "").strip()
    if not program:
        raise ValueError("NOT_FOUND")
    if "community" not in program.get("allowedParticipantTypes", []) or not organisation_id or len(note) > 1000:
        raise ValueError("VALIDATION_ERROR")
    if not find_membership(actor["id"], organisation_id):
        raise ValueError("FORBIDDEN")
    if any(row.get("programId") == program_id and row.get("organisationId") == organisation_id for row in enrollments_for_user(actor["id"])):
        raise ValueError("ALREADY_JOINED")
    application, created = create_program_application({"programId": program_id, "userId": actor["id"], "organisationId": organisation_id, "note": note, "status": "pending"})
    return {"application": _shape_application(application), "created": created}


def organisation_program_applications(actor: dict, organisation_id: str) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    return {"applications": [_shape_application(row) for row in applications_for_organisation(organisation_id)]}


def review_program_application(actor: dict, organisation_id: str, application_id: str, body: dict) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    application = find_program_application(application_id)
    decision = str(body.get("status") or "").lower()
    if not application or application.get("organisationId") != organisation_id:
        raise ValueError("NOT_FOUND")
    if decision not in {"approved", "rejected"} or application.get("status") != "pending":
        raise ValueError("VALIDATION_ERROR")
    program = find_program(application.get("programId"))
    if not program or "community" not in program.get("allowedParticipantTypes", []):
        raise ValueError("NOT_FOUND")
    if not find_membership(application.get("userId"), organisation_id):
        raise ValueError("FORBIDDEN")
    enrollment = None
    if decision == "approved":
        enrollment, _ = create_enrollment({"programId": application["programId"], "userId": application["userId"], "organisationId": organisation_id, "assignedBy": actor["id"], "source": "approved_application"})
    reviewed = update_program_application(application_id, {"status": decision, "reviewedBy": actor["id"], "reviewedAt": now_iso(), "updatedAt": now_iso()})
    return {"application": _shape_application(reviewed), "enrollment": _shape_enrollment(enrollment) if enrollment else None}


def enroll_self(actor: dict, program_id: str) -> dict:
    program = find_program(program_id)
    if not program:
        raise ValueError("NOT_FOUND")
    if "individual" not in program.get("allowedParticipantTypes", []):
        raise ValueError("FORBIDDEN")
    enrollment, created = create_enrollment(
        {"programId": program_id, "userId": actor["id"], "organisationId": None, "assignedBy": actor["id"], "source": "self"}
    )
    return {"enrollment": _shape_enrollment({**enrollment, "program": program}), "created": created}


def assign_member(actor: dict, organisation_id: str, body: dict) -> dict:
    admin_membership = find_membership(actor["id"], organisation_id)
    if not admin_membership or admin_membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    user_id = str(body.get("userId") or "").strip()
    program_id = str(body.get("programId") or "").strip()
    if not user_id or not program_id:
        raise ValueError("VALIDATION_ERROR")
    member = next((row for row in members_for_org(organisation_id) if row.get("userId") == user_id), None)
    if not member:
        raise ValueError("FORBIDDEN")
    if not find_by_id(user_id):
        raise ValueError("NOT_FOUND")
    program = find_program(program_id)
    if not program:
        raise ValueError("NOT_FOUND")
    if "community" not in program.get("allowedParticipantTypes", []):
        raise ValueError("FORBIDDEN")
    enrollment, created = create_enrollment(
        {
            "programId": program_id,
            "userId": user_id,
            "organisationId": organisation_id,
            "assignedBy": actor["id"],
            "source": "community_admin",
        }
    )
    return {"enrollment": _shape_enrollment({**enrollment, "program": program}), "created": created}


def assign_members(actor: dict, organisation_id: str, body: dict) -> dict:
    admin_membership = find_membership(actor["id"], organisation_id)
    if not admin_membership or admin_membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    program_id = str(body.get("programId") or "").strip()
    user_ids = body.get("userIds")
    if not isinstance(user_ids, list) or not user_ids or len(user_ids) > 100:
        raise ValueError("VALIDATION_ERROR")
    clean_ids = list(dict.fromkeys(str(value or "").strip() for value in user_ids if str(value or "").strip()))
    program = find_program(program_id)
    if not program:
        raise ValueError("NOT_FOUND")
    if "community" not in program.get("allowedParticipantTypes", []):
        raise ValueError("FORBIDDEN")
    member_ids = {row.get("userId") for row in members_for_org(organisation_id)}
    if any(user_id not in member_ids or not find_by_id(user_id) for user_id in clean_ids):
        raise ValueError("FORBIDDEN")
    results = []
    for user_id in clean_ids:
        enrollment, created = create_enrollment({"programId": program_id, "userId": user_id, "organisationId": organisation_id, "assignedBy": actor["id"], "source": "community_admin"})
        results.append({"enrollment": _shape_enrollment({**enrollment, "program": program}), "created": created})
    return {"results": results, "createdCount": sum(row["created"] for row in results)}


def community_program_context(actor: dict, organisation_id: str) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership:
        raise ValueError("FORBIDDEN")
    members = []
    for row in members_for_org(organisation_id):
        user = find_by_id(row.get("userId", "")) or {}
        members.append({"membershipId": row["id"], "userId": row.get("userId"), "name": user.get("name", "Community member"), "role": row.get("role")})
    linked_ids = {row.get("programId") for row in enrollments_for_organisation(organisation_id)}
    unique_programs = {row["id"]: row for row in list_programs() if row.get("organisationId") == organisation_id or row.get("id") in linked_ids}
    return {
        "membership": membership,
        "members": members,
        "programs": [_public_program(row) for row in unique_programs.values()],
        "enrollments": [_shape_enrollment(row) for row in enrollments_for_organisation(organisation_id)],
        "permissions": {"canAssignPrograms": membership.get("role") in {"OWNER", "ADMIN"}, "canManagePrograms": membership.get("role") in {"OWNER", "ADMIN"}},
    }


def save_community_program(actor: dict, organisation_id: str, body: dict, program_id: str | None = None) -> dict:
    membership = find_membership(actor["id"], organisation_id)
    if not membership or membership.get("role") not in {"OWNER", "ADMIN"}:
        raise ValueError("FORBIDDEN")
    title = str(body.get("title") or "").strip()
    summary = str(body.get("summary") or "").strip()
    if len(title) < 2 or len(summary) < 2:
        raise ValueError("VALIDATION_ERROR")
    values = {"title": title, "summary": summary, "description": str(body.get("description") or "").strip(), "participationInfo": str(body.get("participationInfo") or "").strip(), "region": str(body.get("region") or "").strip(), "conservationGoal": str(body.get("conservationGoal") or "").strip(), "status": "published", "allowedParticipantTypes": ["community"], "organisationId": organisation_id, "updatedAt": now_iso()}
    if program_id:
        existing = find_program(program_id)
        linked = any(row.get("programId") == program_id for row in enrollments_for_organisation(organisation_id))
        if not existing or (existing.get("organisationId") not in {None, organisation_id} and not linked): raise ValueError("FORBIDDEN")
        saved = update_program(program_id, values)
    else:
        saved = create_program(values)
    return {"program": _public_program(saved)}


def _shape_enrollment(row: dict) -> dict:
    user = find_by_id(row.get("userId", "")) or {}
    program = row.get("program") or find_program(row.get("programId", "")) or {}
    return {
        "id": row.get("id"),
        "programId": row.get("programId"),
        "userId": row.get("userId"),
        "organisationId": row.get("organisationId"),
        "source": row.get("source"),
        "createdAt": row.get("createdAt"),
        "participant": {"id": row.get("userId"), "name": user.get("name", "Participant")},
        "program": _public_program(program) if program else None,
    }


def _shape_application(row: dict) -> dict:
    user = find_by_id(row.get("userId", "")) or {}
    program = find_program(row.get("programId", "")) or {}
    return {
        "id": row.get("id"), "programId": row.get("programId"), "organisationId": row.get("organisationId"),
        "status": row.get("status"), "note": row.get("note", ""), "createdAt": row.get("createdAt"),
        "reviewedAt": row.get("reviewedAt"),
        "applicant": {"id": row.get("userId"), "name": user.get("name", "Applicant"), "email": user.get("email", "")},
        "program": _public_program(program) if program else None,
    }
