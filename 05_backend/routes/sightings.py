from __future__ import annotations

from api.errors import error_body, success_body
from auth.middleware import require_auth
from services.sighting_service import community_sightings, create, my_sightings, public_sightings, sighting_detail


def _error(exc):
    code = str(exc)
    if code == "FORBIDDEN":
        return 403, error_body("FORBIDDEN", "You cannot submit or view sightings for this community.")
    if code in {"NOT_FOUND", "COMMUNITY_NOT_FOUND"}:
        return 404, error_body("NOT_FOUND", "Sighting or community not found.")
    if code == "INVALID_SPECIES":
        return 400, error_body("INVALID_SPECIES", "Select a valid species from the knowledge base.")
    return 400, error_body("VALIDATION_ERROR", "Invalid sighting report data.")


def index():
    try:
        return 200, success_body(public_sightings())
    except Exception:
        return 500, error_body("DATA_ERROR", "Sighting reports are unavailable.")


def detail(sighting_id):
    try:
        return 200, success_body(sighting_detail(sighting_id))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Sighting report is unavailable.")


def mine(handler):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(my_sightings(actor))
    except Exception:
        return 500, error_body("DATA_ERROR", "Your sighting reports are unavailable.")


def community(handler, organisation_id):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 200, success_body(community_sightings(actor, organisation_id))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "Community sightings are unavailable.")


def post(handler, body):
    actor, err = require_auth(handler)
    if err:
        return 401, err
    try:
        return 201, success_body(create(actor, body))
    except ValueError as exc:
        return _error(exc)
    except Exception:
        return 500, error_body("DATA_ERROR", "The sighting report could not be saved.")
