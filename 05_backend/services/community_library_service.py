from __future__ import annotations

from models.community_repository import find_organisation, members_for_org, memberships_for_user
from models.contribution_repository import list_for_author
from models.conservation_program_repository import enrollments_for_organisation
from models.user_repository import find_by_id
from services.contribution_service import public_contributions
from services.sighting_service import public_community_sightings, public_member_sightings


def _community(organisation_id: str) -> dict:
    organisation = find_organisation(organisation_id)
    if not organisation or organisation.get("status") != "approved":
        raise ValueError("NOT_FOUND")
    return organisation


def _member(user_id: str) -> tuple[dict, list[dict]]:
    user = find_by_id(user_id)
    memberships = memberships_for_user(user_id)
    # School identities remain private even if a student was attached to a community.
    if not user or user.get("role") != "PUBLIC" or not memberships:
        raise ValueError("NOT_FOUND")
    return user, memberships


def _member_projection(user: dict, memberships: list[dict]) -> dict:
    profile = user.get("publicProfile") if isinstance(user.get("publicProfile"), dict) else {}
    return {
        "id": user.get("id"),
        "name": user.get("name", "Community member"),
        "location": str(profile.get("location") or ""),
        "bio": str(profile.get("bio") or ""),
        "avatarId": str(profile.get("avatarId") or ""),
        "avatarUrl": str(profile.get("avatarUrl") or ""),
        "interestSpecies": [str(value) for value in profile.get("interestSpecies", []) if str(value).strip()][:12],
        "communities": [
            {
                "id": row.get("organisationId"),
                "name": row.get("organisation", {}).get("name", "Community"),
                "role": row.get("role", "MEMBER"),
                "joinedAt": row.get("createdAt"),
            }
            for row in memberships
        ],
    }


def _library_items(organisation_id: str) -> list[dict]:
    contributions = [row for row in public_contributions(organisation_id)["contributions"] if row.get("libraryStatus") == "approved"]
    sightings = public_community_sightings(organisation_id)
    items = [
        {
            "id": row["id"],
            "resourceType": "contribution",
            "contentType": row.get("type"),
            "title": row.get("title"),
            "summary": row.get("body", "")[:280],
            "createdAt": row.get("createdAt"),
            "author": row.get("author"),
        }
        for row in contributions
    ]
    items.extend(
        {
            "id": row["id"],
            "resourceType": "sighting",
            "contentType": "sighting-report",
            "title": f"{row.get('species', {}).get('name', 'Species')} sighting",
            "summary": row.get("notes", "")[:280],
            "createdAt": row.get("createdAt"),
            "author": row.get("author"),
            "species": row.get("species"),
            "publicPlace": row.get("publicPlace"),
            "verificationStatus": row.get("verificationStatus"),
        }
        for row in sightings
    )
    return sorted(items, key=lambda row: row.get("createdAt") or "", reverse=True)


def community_library(organisation_id: str) -> dict:
    organisation = _community(organisation_id)
    return {"community": {key: organisation.get(key) for key in ("id", "name", "bio", "region", "logoUrl", "coverImageUrl")}, "items": _library_items(organisation_id)}


def community_public_profile(organisation_id: str) -> dict:
    organisation = _community(organisation_id)
    members = []
    for membership in members_for_org(organisation_id):
        user = find_by_id(membership.get("userId", "")) or {}
        if user.get("role") == "PUBLIC":
            members.append({"id": user.get("id"), "name": user.get("name", "Community member"), "role": membership.get("role", "MEMBER")})
    items = _library_items(organisation_id)
    programs = {}
    for enrollment in enrollments_for_organisation(organisation_id):
        program = enrollment.get("program") or {}
        if program.get("id"):
            programs[program["id"]] = {key: program.get(key) for key in ("id", "title", "summary", "region", "participationInfo")}
    return {
        "community": {key: organisation.get(key) for key in ("id", "name", "bio", "region", "logoUrl", "coverImageUrl")},
        "members": members,
        "librarySummary": {
            "total": len(items),
            "contributions": sum(row["resourceType"] == "contribution" for row in items),
            "sightings": sum(row["resourceType"] == "sighting" for row in items),
        },
        "recentItems": items[:4],
        "programs": list(programs.values()),
    }


def member_public_profile(user_id: str) -> dict:
    user, memberships = _member(user_id)
    contributions = member_public_contributions(user_id)["items"]
    return {"member": _member_projection(user, memberships), "contributionSummary": {"total": len(contributions), "articles": sum(row["resourceType"] == "contribution" for row in contributions), "sightings": sum(row["resourceType"] == "sighting" for row in contributions)}, "recentItems": contributions[:4]}


def member_public_contributions(user_id: str) -> dict:
    user, memberships = _member(user_id)
    allowed_orgs = {row.get("organisationId") for row in memberships}
    articles = [
        row for row in list_for_author(user_id)
        if row.get("status") == "published" and row.get("organisationId") in allowed_orgs
    ]
    public_author = {"id": user.get("id"), "name": user.get("name", "Community member")}
    items = [{"id": row.get("id"), "resourceType": "contribution", "contentType": row.get("type"), "title": row.get("title"), "summary": row.get("body", "")[:280], "createdAt": row.get("createdAt"), "communityId": row.get("organisationId"), "author": public_author} for row in articles]
    items.extend({"id": row.get("id"), "resourceType": "sighting", "contentType": "sighting-report", "title": f"{row.get('species', {}).get('name', 'Species')} sighting", "summary": row.get("notes", "")[:280], "createdAt": row.get("createdAt"), "communityId": row.get("community", {}).get("id"), "publicPlace": row.get("publicPlace"), "author": public_author} for row in public_member_sightings(user_id) if row.get("community", {}).get("id") in allowed_orgs)
    return {"member": {"id": user.get("id"), "name": user.get("name", "Community member")}, "items": sorted(items, key=lambda row: row.get("createdAt") or "", reverse=True)}
