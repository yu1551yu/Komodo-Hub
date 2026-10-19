from __future__ import annotations

from api.errors import error_body, success_body
from models.species_repository import get_species, list_species


def index(query: str = ""):
    try:
        return 200, success_body({"species": list_species(query)})
    except Exception:
        return 500, error_body("DATA_ERROR", "Species knowledge base is unavailable.")


def detail(species_id: str):
    try:
        row = get_species(species_id)
    except ValueError:
        return 400, error_body("VALIDATION_ERROR", "Invalid species id.")
    except Exception:
        return 500, error_body("DATA_ERROR", "Species knowledge base is unavailable.")
    if not row:
        return 404, error_body("NOT_FOUND", "Species not found.")
    return 200, success_body({"species": row})
