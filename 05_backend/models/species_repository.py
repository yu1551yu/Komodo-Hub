from __future__ import annotations

from models.json_store import DATA_DIR

DATA_FILE = DATA_DIR / "komodo_hub.json"


def _read_app_data() -> dict:
    from database.store import read_species
    return {"species": read_species()}


def _public_species(row: dict) -> dict:
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "latin": str(row.get("latin") or ""),
        "summary": str(row.get("knowledge") or ""),
        "conservationStatus": str(row.get("level") or ""),
        "region": str(row.get("region") or ""),
        "habitat": str(row.get("habitat") or ""),
        "population": str(row.get("population") or ""),
        "threats": str(row.get("threats") or ""),
        "protectionMethods": str(row.get("protectionMethods") or ""),
        "image": row.get("image") or row.get("emoji") or "",
        "accent": str(row.get("accent") or "#6c8b62"),
    }


def list_species(query: str = "") -> list[dict]:
    data = _read_app_data()
    rows = data.get("species") if isinstance(data.get("species"), list) else []
    clean = [_public_species(row) for row in rows if isinstance(row, dict)]
    term = query.strip().lower()
    if not term:
        return clean
    return [
        row
        for row in clean
        if term in " ".join(
            [
                row["name"],
                row["latin"],
                row["summary"],
                row["region"],
                row["habitat"],
                row["threats"],
            ]
        ).lower()
    ]


def get_species(species_id: str) -> dict | None:
    key = str(species_id or "").strip()
    if not key or "/" in key or "\\" in key:
        raise ValueError("INVALID_ID")
    return next((row for row in list_species() if row["id"] == key), None)
