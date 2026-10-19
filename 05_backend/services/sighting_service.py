from __future__ import annotations

from models.community_repository import find_membership, find_organisation
from models.sighting_repository import create_sighting, find_sighting, list_for_author, list_for_organisation, list_public
from models.species_repository import get_species
from models.user_repository import find_by_id


def _shape(row: dict, include_private: bool = False, include_public_author_id: bool = False) -> dict:
    species = get_species(row.get("speciesId", "")) or {}
    author = find_by_id(row.get("authorId", "")) or {}
    org = find_organisation(row.get("organisationId", "")) if row.get("organisationId") else None
    result = {
        "id": row.get("id"),
        "species": {"id": row.get("speciesId"), "name": species.get("name", "Unknown species"), "latin": species.get("latin", ""), "image": species.get("image", "")},
        "notes": row.get("notes", ""),
        "observedAt": row.get("observedAt"),
        "publicPlace": row.get("publicPlace", ""),
        "visibility": row.get("visibility", "public"),
        "verificationStatus": row.get("verificationStatus", "unverified"),
        "createdAt": row.get("createdAt"),
        "author": {"name": author.get("name", "Citizen observer")},
        "community": {"id": org.get("id"), "name": org.get("name")} if org else None,
        "libraryStatus": row.get("libraryStatus", "approved" if org else None),
        "reviewReason": row.get("reviewReason", ""),
    }
    if include_private:
        result["preciseLocation"] = row.get("preciseLocation", "")
        result["author"]["id"] = row.get("authorId")
    elif include_public_author_id and author.get("role") == "PUBLIC":
        result["author"]["id"] = row.get("authorId")
    return result


def public_sightings() -> dict:
    return {"sightings": [_shape(row) for row in list_public()]}


def public_community_sightings(organisation_id: str) -> list[dict]:
    return [_shape(row, include_public_author_id=True) for row in list_for_organisation(organisation_id) if row.get("visibility") == "public" and row.get("libraryStatus", "approved") == "approved"]


def public_member_sightings(user_id: str) -> list[dict]:
    return [
        _shape(row)
        for row in list_for_author(user_id)
        if row.get("visibility") == "public" and row.get("organisationId")
    ]


def sighting_detail(sighting_id: str) -> dict:
    row = find_sighting(sighting_id)
    if not row or row.get("visibility") != "public":
        raise ValueError("NOT_FOUND")
    return {"sighting": _shape(row, include_public_author_id=bool(row.get("organisationId")))}


def my_sightings(actor: dict) -> dict:
    return {"sightings": [_shape(row, True) for row in list_for_author(actor["id"])]}


def community_sightings(actor: dict, organisation_id: str) -> dict:
    if not find_organisation(organisation_id):
        raise ValueError("COMMUNITY_NOT_FOUND")
    if not find_membership(actor["id"], organisation_id):
        raise ValueError("FORBIDDEN")
    return {"sightings": [_shape(row, True) for row in list_for_organisation(organisation_id)]}


def create(actor: dict, body: dict) -> dict:
    species_id = str(body.get("speciesId") or "").strip()
    if not get_species(species_id):
        raise ValueError("INVALID_SPECIES")
    organisation_id = str(body.get("organisationId") or "").strip() or None
    if organisation_id and not find_membership(actor["id"], organisation_id):
        raise ValueError("FORBIDDEN")
    row = create_sighting(actor["id"], body, organisation_id)
    return {"sighting": _shape(row, True)}
