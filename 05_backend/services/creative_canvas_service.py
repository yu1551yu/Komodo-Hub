from __future__ import annotations

from models.conservation_program_repository import find_program
from models.contribution_repository import find_contribution, list_for_author as author_contributions
from models.json_store import new_id, now_iso, read_rows, write_rows
from models.sighting_repository import find_sighting, list_for_author as author_sightings
from models.species_repository import get_species


FILE = "creative_canvas_items.json"
RESOURCE_TYPES = {"contribution", "sighting"}


def _program(row: dict) -> dict | None:
    program_id = str(row.get("programId") or "").strip()
    if not program_id:
        return None
    program = find_program(program_id)
    if not program:
        return None
    return {key: program.get(key) for key in ("id", "title", "summary")}


def _resource(owner_id: str, resource_type: str, resource_id: str) -> dict:
    if resource_type == "contribution":
        row = find_contribution(resource_id)
        if not row or row.get("authorId") != owner_id:
            raise ValueError("NOT_FOUND")
        return {
            "id": row.get("id"),
            "resourceType": resource_type,
            "contentType": row.get("type"),
            "title": row.get("title"),
            "summary": row.get("body", "")[:240],
            "content": row.get("body", ""),
            "createdAt": row.get("createdAt"),
            "communityId": row.get("organisationId"),
            "visibility": "public",
            "media": None,
            "program": _program(row),
        }
    if resource_type == "sighting":
        row = find_sighting(resource_id)
        if not row or row.get("authorId") != owner_id:
            raise ValueError("NOT_FOUND")
        species = get_species(row.get("speciesId", "")) or {}
        return {
            "id": row.get("id"),
            "resourceType": resource_type,
            "contentType": "sighting-report",
            "title": f"{species.get('name', 'Species')} sighting",
            "summary": row.get("notes", "")[:240],
            "content": row.get("notes", ""),
            "createdAt": row.get("createdAt"),
            "observedAt": row.get("observedAt"),
            "publicPlace": row.get("publicPlace", ""),
            "communityId": row.get("organisationId"),
            "visibility": row.get("visibility", "public"),
            "media": species.get("image") or None,
            "program": _program(row),
        }
    raise ValueError("INVALID_RESOURCE_TYPE")


def _owner_rows(owner_id: str) -> list[dict]:
    return sorted(
        [row for row in read_rows(FILE) if row.get("ownerId") == owner_id],
        key=lambda row: (int(row.get("displayOrder", 0)), row.get("createdAt", "")),
    )


def _shape(owner_id: str, row: dict) -> dict:
    return {
        "id": row.get("id"),
        "displayOrder": row.get("displayOrder", 0),
        "createdAt": row.get("createdAt"),
        "resource": _resource(owner_id, row.get("resourceType", ""), row.get("resourceId", "")),
    }


def my_canvas(owner_id: str) -> dict:
    items = []
    for row in _owner_rows(owner_id):
        try:
            items.append(_shape(owner_id, row))
        except ValueError:
            # Keep stale references out of the UI without mutating data during reads.
            continue
    return {"items": items}


def candidates(owner_id: str) -> dict:
    selected = {(row.get("resourceType"), row.get("resourceId")) for row in _owner_rows(owner_id)}
    resources = []
    for row in author_contributions(owner_id):
        if row.get("status") == "published":
            item = _resource(owner_id, "contribution", row["id"])
            item["alreadyAdded"] = ("contribution", row["id"]) in selected
            resources.append(item)
    for row in author_sightings(owner_id):
        item = _resource(owner_id, "sighting", row["id"])
        item["alreadyAdded"] = ("sighting", row["id"]) in selected
        resources.append(item)
    resources.sort(key=lambda row: row.get("createdAt") or "", reverse=True)
    return {"items": resources}


def add_items(owner_id: str, body: dict) -> dict:
    selections = body.get("items")
    if not isinstance(selections, list) or not selections or len(selections) > 100:
        raise ValueError("INVALID_SELECTION")
    rows = read_rows(FILE)
    owner_rows = _owner_rows(owner_id)
    existing = {(row.get("resourceType"), row.get("resourceId")) for row in owner_rows}
    added = []
    next_order = len(owner_rows)
    now = now_iso()
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("INVALID_SELECTION")
        resource_type = str(selection.get("resourceType") or "").strip()
        resource_id = str(selection.get("resourceId") or "").strip()
        if resource_type not in RESOURCE_TYPES:
            raise ValueError("INVALID_RESOURCE_TYPE")
        _resource(owner_id, resource_type, resource_id)
        key = (resource_type, resource_id)
        if key in existing:
            continue
        row = {
            "id": new_id("canvas"),
            "ownerId": owner_id,
            "resourceType": resource_type,
            "resourceId": resource_id,
            "displayOrder": next_order,
            "createdAt": now,
            "updatedAt": now,
        }
        rows.append(row)
        added.append(_shape(owner_id, row))
        existing.add(key)
        next_order += 1
    if added:
        write_rows(FILE, rows)
    return {"added": added, "items": my_canvas(owner_id)["items"]}


def canvas_item(owner_id: str, item_id: str) -> dict:
    row = next((row for row in _owner_rows(owner_id) if row.get("id") == item_id), None)
    if not row:
        raise ValueError("NOT_FOUND")
    return {"item": _shape(owner_id, row)}


def remove_item(owner_id: str, item_id: str) -> dict:
    rows = read_rows(FILE)
    target = next((row for row in rows if row.get("id") == item_id and row.get("ownerId") == owner_id), None)
    if not target:
        raise ValueError("NOT_FOUND")
    remaining = [row for row in rows if row.get("id") != item_id]
    owner_remaining = sorted(
        [row for row in remaining if row.get("ownerId") == owner_id],
        key=lambda row: int(row.get("displayOrder", 0)),
    )
    order_by_id = {row["id"]: index for index, row in enumerate(owner_remaining)}
    for row in remaining:
        if row.get("id") in order_by_id:
            row["displayOrder"] = order_by_id[row["id"]]
            row["updatedAt"] = now_iso()
    write_rows(FILE, remaining)
    return {"removed": True, "items": my_canvas(owner_id)["items"]}


def reorder(owner_id: str, body: dict) -> dict:
    item_ids = body.get("itemIds")
    owner_rows = _owner_rows(owner_id)
    expected = {row.get("id") for row in owner_rows}
    if not isinstance(item_ids, list) or len(item_ids) != len(set(item_ids)) or set(item_ids) != expected:
        raise ValueError("INVALID_ORDER")
    order_by_id = {item_id: index for index, item_id in enumerate(item_ids)}
    rows = read_rows(FILE)
    now = now_iso()
    for row in rows:
        if row.get("ownerId") == owner_id:
            row["displayOrder"] = order_by_id[row["id"]]
            row["updatedAt"] = now
    write_rows(FILE, rows)
    return my_canvas(owner_id)
