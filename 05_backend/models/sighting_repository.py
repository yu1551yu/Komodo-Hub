from __future__ import annotations

from html import escape

from models.work_repository import create_row, find_row, list_rows, update_row

FILE = "species_sightings.json"
VISIBILITIES = {"public", "community", "private"}


def _text(value, limit: int, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and len(text) < 2:
        raise ValueError("REQUIRED")
    if len(text) > limit:
        raise ValueError("TOO_LONG")
    return escape(text, quote=True)


def create_sighting(author_id: str, body: dict, organisation_id: str | None) -> dict:
    visibility = str(body.get("visibility") or "public").strip().lower()
    if visibility not in VISIBILITIES:
        raise ValueError("INVALID_VISIBILITY")
    if visibility == "community" and not organisation_id:
        raise ValueError("COMMUNITY_REQUIRED")
    observed_at = str(body.get("observedAt") or "").strip()
    if len(observed_at) < 10 or len(observed_at) > 35:
        raise ValueError("INVALID_DATE")
    return create_row(
        FILE,
        "sighting",
        {
            "speciesId": str(body.get("speciesId") or "").strip(),
            "authorId": author_id,
            "organisationId": organisation_id,
            "notes": _text(body.get("notes"), 5000, True),
            "observedAt": observed_at,
            "publicPlace": _text(body.get("publicPlace"), 160, True),
            "preciseLocation": _text(body.get("preciseLocation"), 300),
            "visibility": visibility,
            "verificationStatus": "unverified",
            "libraryStatus": "pending" if organisation_id else None,
            "reviewReason": "",
            "reviewedBy": None,
            "reviewedAt": None,
        },
    )


def find_sighting(sighting_id: str) -> dict | None:
    key = str(sighting_id or "").strip()
    if not key or "/" in key or "\\" in key:
        raise ValueError("INVALID_ID")
    return find_row(FILE, key)


def list_public() -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("visibility") == "public"],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def list_for_author(author_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("authorId") == author_id],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def list_for_organisation(organisation_id: str) -> list[dict]:
    return sorted(
        [row for row in list_rows(FILE) if row.get("organisationId") == organisation_id],
        key=lambda row: row.get("createdAt", ""),
        reverse=True,
    )


def update_library_review(sighting_id: str, values: dict) -> dict | None:
    return update_row(FILE, sighting_id, values, {"libraryStatus", "reviewReason", "reviewedBy", "reviewedAt"})
